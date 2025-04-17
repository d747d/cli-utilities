#!/usr/bin/env python3
"""
PostgreSQL Database Visualizer
------------------------------
Visualizes PostgreSQL database structure, performance metrics, and potential issues,
with support for cstore files and certificate-based authentication.
"""

import os
import sys
import argparse
import logging
import json
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
from tabulate import tabulate
import psycopg2
from psycopg2 import sql
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class PostgresVisualizer:
    def __init__(self, host, port, dbname, user, password=None, 
                 cert_path=None, key_path=None, ca_cert_path=None):
        """
        Initialize the PostgreSQL visualizer with connection parameters.
        
        Parameters:
        -----------
        host : str
            Database server hostname
        port : int
            Database server port
        dbname : str
            Database name
        user : str
            Database user
        password : str, optional
            Database password (not needed if using cert authentication)
        cert_path : str, optional
            Path to client certificate file
        key_path : str, optional 
            Path to client key file
        ca_cert_path : str, optional
            Path to CA certificate file
        """
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password
        self.cert_path = cert_path
        self.key_path = key_path
        self.ca_cert_path = ca_cert_path
        self.conn = None
        self.data = {
            'tables': [],
            'cstore_tables': [],
            'indexes': [],
            'relationships': [],
            'performance': {},
            'locks': [],
            'vacuum_status': [],
            'bloat_analysis': [],
            'table_io_stats': [],
            'index_usage': []
        }
        
    def connect(self):
        """Establish connection to PostgreSQL database using certs if provided."""
        try:
            conn_params = {
                'host': self.host,
                'port': self.port,
                'dbname': self.dbname,
                'user': self.user
            }
            
            # Add password if provided
            if self.password:
                conn_params['password'] = self.password
                
            # Add SSL parameters if certificate paths are provided
            if self.cert_path and self.key_path:
                conn_params['sslmode'] = 'verify-ca' if self.ca_cert_path else 'require'
                conn_params['sslcert'] = self.cert_path
                conn_params['sslkey'] = self.key_path
                if self.ca_cert_path:
                    conn_params['sslrootcert'] = self.ca_cert_path
            
            self.conn = psycopg2.connect(**conn_params)
            logger.info(f"Successfully connected to {self.dbname} at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            return False
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def collect_database_info(self):
        """Collect all information about the database."""
        if not self.conn:
            if not self.connect():
                return False
                
        # Set autocommit to True to prevent transaction blocks
        self.conn.autocommit = True
        
        self._collect_tables_info()
        self._collect_cstore_tables()
        self._collect_indexes_info()
        self._collect_relationships()
        self._collect_performance_metrics()
        self._collect_locks_info()
        self._collect_vacuum_status()
        self._collect_bloat_analysis()
        self._collect_table_io_stats()
        self._collect_index_usage()
        
        return True
    
    def _collect_tables_info(self):
        """Collect information about all tables in the database."""
        logger.info("Collecting tables information...")
        
        query = """
        SELECT 
            n.nspname as schema,
            c.relname as table_name,
            c.reltuples as row_estimate,
            pg_size_pretty(pg_total_relation_size(c.oid)) as total_size,
            pg_size_pretty(pg_relation_size(c.oid)) as table_size,
            pg_size_pretty(pg_total_relation_size(c.oid) - pg_relation_size(c.oid)) as index_size,
            pg_total_relation_size(c.oid) as size_bytes,
            to_char(c.reltuples, 'FM999,999,999,999') as row_count,
            obj_description(c.oid, 'pg_class') as description,
            c.relfrozenxid::text as frozen_xid,
            c.relminmxid::text as min_mxid,
            c.relkind as kind
        FROM 
            pg_class c
        JOIN 
            pg_namespace n ON c.relnamespace = n.oid
        WHERE 
            c.relkind IN ('r', 'p')
            AND n.nspname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY 
            pg_total_relation_size(c.oid) DESC;
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query)
            self.data['tables'] = [dict(zip([col[0] for col in cur.description], row)) 
                                  for row in cur.fetchall()]
            
        logger.info(f"Collected information for {len(self.data['tables'])} tables")
    
    def _collect_cstore_tables(self):
        """Collect information about cstore tables if the extension is available."""
        logger.info("Checking for cstore extension and tables...")
        
        # First check if cstore extension is installed
        extension_query = """
        SELECT count(*) FROM pg_extension WHERE extname = 'cstore_fdw';
        """
        
        with self.conn.cursor() as cur:
            cur.execute(extension_query)
            extension_exists = cur.fetchone()[0] > 0
            
        if not extension_exists:
            logger.info("cstore_fdw extension is not installed")
            return
            
        # Query cstore tables
        cstore_query = """
        SELECT 
            n.nspname as schema,
            c.relname as table_name,
            c.reltuples as row_estimate,
            pg_size_pretty(pg_relation_size(c.oid)) as size,
            pg_relation_size(c.oid) as size_bytes,
            to_char(c.reltuples, 'FM999,999,999,999') as row_count,
            obj_description(c.oid, 'pg_class') as description,
            array_to_string(array(
                SELECT a.attname 
                FROM pg_attribute a 
                WHERE a.attrelid = c.oid AND a.attnum > 0 
                ORDER BY a.attnum
            ), ',') as columns
        FROM 
            pg_class c
        JOIN 
            pg_namespace n ON c.relnamespace = n.oid
        JOIN 
            pg_foreign_table ft ON c.oid = ft.ftrelid
        JOIN 
            pg_foreign_server fs ON ft.ftserver = fs.oid
        WHERE 
            fs.srvname = 'cstore_server'
        ORDER BY 
            pg_relation_size(c.oid) DESC;
        """
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(cstore_query)
                self.data['cstore_tables'] = [dict(zip([col[0] for col in cur.description], row)) 
                                            for row in cur.fetchall()]
                
            logger.info(f"Collected information for {len(self.data['cstore_tables'])} cstore tables")
        except psycopg2.Error as e:
            logger.warning(f"Could not collect cstore tables: {str(e)}")
    
    def _collect_indexes_info(self):
        """Collect information about all indexes in the database."""
        logger.info("Collecting indexes information...")
        
        query = """
        SELECT
            n.nspname as schema,
            t.relname as table_name,
            i.relname as index_name,
            a.attname as column_name,
            ix.indisunique as is_unique,
            ix.indisprimary as is_primary,
            pg_size_pretty(pg_relation_size(i.oid)) as index_size,
            pg_relation_size(i.oid) as size_bytes,
            am.amname as index_type,
            CASE
                WHEN ix.indpred IS NOT NULL THEN 'Partial'
                ELSE 'Normal'
            END as index_kind,
            pg_get_indexdef(ix.indexrelid) as definition
        FROM
            pg_index ix
        JOIN
            pg_class i ON i.oid = ix.indexrelid
        JOIN
            pg_class t ON t.oid = ix.indrelid
        JOIN
            pg_namespace n ON n.oid = t.relnamespace
        JOIN
            pg_am am ON i.relam = am.oid
        JOIN
            pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
        WHERE
            n.nspname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY
            n.nspname, t.relname, i.relname, a.attname;
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query)
            self.data['indexes'] = [dict(zip([col[0] for col in cur.description], row)) 
                                   for row in cur.fetchall()]
            
        logger.info(f"Collected information for {len(self.data['indexes'])} indexes")
    
    def _collect_relationships(self):
        """Collect foreign key relationships between tables."""
        logger.info("Collecting table relationships...")
        
        query = """
        SELECT
            ns.nspname AS source_schema,
            cl.relname AS source_table,
            att.attname AS source_column,
            nf.nspname AS target_schema,
            clf.relname AS target_table,
            attf.attname AS target_column,
            con.conname AS constraint_name
        FROM
            pg_constraint con
            JOIN pg_class cl ON con.conrelid = cl.oid
            JOIN pg_namespace ns ON cl.relnamespace = ns.oid
            JOIN pg_attribute att ON att.attrelid = cl.oid AND att.attnum = con.conkey[1]
            JOIN pg_class clf ON con.confrelid = clf.oid
            JOIN pg_namespace nf ON clf.relnamespace = nf.oid
            JOIN pg_attribute attf ON attf.attrelid = clf.oid AND attf.attnum = con.confkey[1]
        WHERE
            con.contype = 'f'
            AND ns.nspname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY
            ns.nspname, cl.relname, att.attname;
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query)
            self.data['relationships'] = [dict(zip([col[0] for col in cur.description], row)) 
                                         for row in cur.fetchall()]
            
        logger.info(f"Collected information for {len(self.data['relationships'])} relationships")
    
    def _collect_performance_metrics(self):
        """Collect various performance metrics for the database."""
        logger.info("Collecting performance metrics...")
        
        # Database size
        size_query = """
        SELECT pg_size_pretty(pg_database_size(current_database())) as db_size,
               pg_database_size(current_database()) as size_bytes;
        """
        
        # Connection stats
        connection_query = """
        SELECT 
            datname, 
            numbackends as connections,
            xact_commit as commits,
            xact_rollback as rollbacks,
            blks_read,
            blks_hit,
            tup_returned,
            tup_fetched,
            tup_inserted,
            tup_updated,
            tup_deleted,
            CASE WHEN blks_read + blks_hit > 0 
                 THEN round(100 * blks_hit / (blks_read + blks_hit), 2)
                 ELSE 0 
            END as cache_hit_ratio
        FROM 
            pg_stat_database
        WHERE 
            datname = current_database();
        """
        
        # Query stats
        query_stats = """
        SELECT 
            round(total_exec_time::numeric, 2) as total_time,
            calls,
            round(mean_exec_time::numeric, 2) as mean_time,
            round(stddev_exec_time::numeric, 2) as stddev_time,
            rows,
            query
        FROM 
            pg_stat_statements
        ORDER BY 
            total_exec_time DESC
        LIMIT 20;
        """
        
        # WAL stats
        wal_stats = """
        SELECT 
            pg_current_wal_lsn() as current_wal_lsn,
            pg_walfile_name(pg_current_wal_lsn()) as current_wal_file,
            pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')) as wal_size
        """
        
        with self.conn.cursor() as cur:
            # Database size
            cur.execute(size_query)
            self.data['performance']['db_size'] = dict(zip([col[0] for col in cur.description], 
                                                          cur.fetchone()))
            
            # Connection stats
            cur.execute(connection_query)
            self.data['performance']['connection_stats'] = dict(zip([col[0] for col in cur.description], 
                                                                   cur.fetchone()))
            
            # Try to get query stats if pg_stat_statements is available
            try:
                cur.execute(query_stats)
                self.data['performance']['query_stats'] = [dict(zip([col[0] for col in cur.description], row)) 
                                                         for row in cur.fetchall()]
            except psycopg2.Error:
                logger.warning("pg_stat_statements extension not available, skipping query stats")
                self.data['performance']['query_stats'] = []
            
            # Try to get WAL stats (requires superuser permissions)
            try:
                cur.execute(wal_stats)
                self.data['performance']['wal_stats'] = dict(zip([col[0] for col in cur.description], 
                                                               cur.fetchone()))
            except psycopg2.Error:
                logger.warning("Could not collect WAL stats (requires higher permissions)")
                self.data['performance']['wal_stats'] = {}
                
        logger.info("Collected performance metrics")
        
    def _collect_locks_info(self):
        """Collect information about locks in the database."""
        logger.info("Collecting locks information...")
        
        query = """
        SELECT 
            pg_class.relname as table_name,
            pg_namespace.nspname as schema,
            mode,
            granted,
            extract(epoch from now() - query_start)::integer as query_duration_sec,
            pid,
            usename as username,
            state,
            query
        FROM 
            pg_locks
        JOIN 
            pg_class ON pg_locks.relation = pg_class.oid
        JOIN 
            pg_namespace ON pg_class.relnamespace = pg_namespace.oid
        JOIN 
            pg_stat_activity ON pg_locks.pid = pg_stat_activity.pid
        WHERE 
            pg_class.relkind = 'r'::char
            AND pg_namespace.nspname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY 
            query_duration_sec DESC;
        """
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                self.data['locks'] = [dict(zip([col[0] for col in cur.description], row)) 
                                    for row in cur.fetchall()]
                
            logger.info(f"Collected information for {len(self.data['locks'])} locks")
        except Exception as e:
            logger.warning(f"Could not collect locks information: {str(e)}")
            self.data['locks'] = []
    
    def _collect_vacuum_status(self):
        """Collect information about vacuum status for tables."""
        logger.info("Collecting vacuum status information...")
        
        query = """
        SELECT
            n.nspname as schema,
            c.relname as table_name,
            to_char(COALESCE(pg_stat_get_last_vacuum_time(c.oid), 
                            pg_stat_get_last_autovacuum_time(c.oid)), 'YYYY-MM-DD HH24:MI:SS') as last_vacuum,
            to_char(COALESCE(pg_stat_get_last_analyze_time(c.oid), 
                            pg_stat_get_last_autoanalyze_time(c.oid)), 'YYYY-MM-DD HH24:MI:SS') as last_analyze,
            pg_stat_get_vacuum_count(c.oid) + pg_stat_get_autovacuum_count(c.oid) as vacuum_count,
            pg_stat_get_analyze_count(c.oid) + pg_stat_get_autoanalyze_count(c.oid) as analyze_count,
            pg_stat_get_live_tuples(c.oid) as live_tuples,
            pg_stat_get_dead_tuples(c.oid) as dead_tuples,
            CASE 
                WHEN pg_stat_get_live_tuples(c.oid) > 0 
                THEN round(100 * pg_stat_get_dead_tuples(c.oid) / pg_stat_get_live_tuples(c.oid), 2) 
                ELSE 0 
            END as dead_tuple_pct,
            c.reloptions as storage_parameters
        FROM
            pg_class c
        JOIN
            pg_namespace n ON c.relnamespace = n.oid
        WHERE
            c.relkind = 'r'
            AND n.nspname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY
            pg_stat_get_dead_tuples(c.oid) DESC;
        """
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                self.data['vacuum_status'] = [dict(zip([col[0] for col in cur.description], row)) 
                                            for row in cur.fetchall()]
                
            logger.info(f"Collected vacuum status for {len(self.data['vacuum_status'])} tables")
        except Exception as e:
            logger.warning(f"Could not collect vacuum status: {str(e)}")
            self.data['vacuum_status'] = []
    
    def _collect_bloat_analysis(self):
        """Collect information about table and index bloat."""
        logger.info("Collecting bloat analysis...")
        
        # Table bloat query
        table_bloat_query = """
        WITH constants AS (
            SELECT 
                current_setting('block_size')::numeric AS bs,
                23 AS hdr,
                8 AS ma
        ),
        no_stats AS (
            SELECT 
                table_schema, 
                table_name, 
                n_live_tup::numeric as est_rows,
                pg_table_size(relid)::numeric as table_size
            FROM 
                information_schema.columns
            JOIN 
                pg_stat_user_tables psut
               ON table_schema = psut.schemaname
              AND table_name = psut.relname
            LEFT OUTER JOIN 
                pg_stats
               ON table_schema = pg_stats.schemaname
              AND table_name = pg_stats.tablename
              AND column_name = attname
            WHERE 
                attname IS NULL
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
            GROUP BY 
                table_schema, table_name, relid, n_live_tup
        ),
        data_headers AS (
            SELECT
                bs, hdr, ma,
                table_schema,
                table_name,
                est_rows,
                table_size,
                (1 - n_null_frac) as notnull_frac,
                avg_width as avg_width
            FROM constants, no_stats as ns
            JOIN pg_stats on ns.table_schema = pg_stats.schemaname
                         and ns.table_name = pg_stats.tablename
            WHERE pg_stats.schemaname NOT IN ('pg_catalog', 'information_schema')
        ),
        bloat_estimation AS (
            SELECT
                schemaname as schema,
                tablename as table_name,
                reltuples::numeric as est_rows,
                relpages::numeric as pages,
                pg_table_size(schemaname||'.'||tablename)::numeric as table_size,
                ROUND(((heappages + toast.relpages) * bs) / (1024^2)) as total_mb,
                ROUND(heappages * bs / (1024^2)) as table_mb,
                ROUND(toast.relpages * bs / (1024^2)) as toast_mb,
                ROUND(1.0 * heappages / relpages, 1) as bloat_ratio,
                CASE WHEN relpages > 0
                   THEN ROUND(((heappages + toast.relpages) * bs - used_bytes) / (1024^2)) 
                   ELSE 0
                END as bloat_mb,
                CASE WHEN relpages > 0
                   THEN ROUND(100 * ((heappages + toast.relpages) * bs - used_bytes) / ((heappages + toast.relpages) * bs)) 
                   ELSE 0
                END as bloat_pct
            FROM
                (SELECT
                    schemaname,
                    tablename,
                    cc.relpages,
                    cc.reltuples,
                    bs,
                    CEIL((cc.reltuples * ((datahdr + ma - (CASE WHEN datahdr % ma = 0 THEN ma ELSE datahdr % ma END)) + nullhdr) + s.field_count) / (bs - 20::float)) as heappages,
                    SUM((1 - s.null_frac) * s.avg_width) as used_bytes
                FROM
                    pg_class cc
                JOIN
                    pg_namespace nn ON cc.relnamespace = nn.oid
                JOIN
                    constants on true
                JOIN
                    (SELECT
                        schemaname,
                        tablename,
                        hdr + 1 + (s.field_count + 7) / 8 as nullhdr,
                        SUM((1 - s.null_frac) * s.avg_width) as datahdr,
                        MAX(s.null_frac) as maxfracsum,
                        COUNT(*) as field_count
                    FROM
                        pg_stats s
                    WHERE
                        s.schemaname NOT IN ('pg_catalog', 'information_schema')
                    GROUP BY
                        1, 2, nullhdr) as s
                ON
                    s.schemaname = nn.nspname
                AND
                    s.tablename = cc.relname
                WHERE
                    cc.relkind = 'r'
                GROUP BY
                    1, 2, 3, 4, 5, heappages) as foo
            JOIN
                pg_stat_user_tables psut
            ON
                psut.schemaname = foo.schemaname
            AND
                psut.relname = foo.tablename
            JOIN
                constants c ON true
            LEFT OUTER JOIN
                (SELECT
                    relname,
                    relpages
                FROM
                    pg_class
                WHERE
                    relkind = 't') as toast
            ON
                toast.relname = 'pg_toast_' || foo.schemaname || '_' || oid(foo.tablename)::text
            ORDER BY
                bloat_mb DESC
        )
        SELECT * FROM bloat_estimation WHERE bloat_pct > 30 ORDER BY bloat_mb DESC LIMIT 100;
        """
        
        # Index bloat query (simplified version)
        index_bloat_query = """
        SELECT
            schemaname as schema,
            tablename as table_name,
            indexname as index_name,
            pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
            pg_relation_size(indexrelid) as size_bytes,
            indexrelid::regclass as index,
            idx_scan as scans,
            idx_tup_read as reads,
            idx_tup_fetch as fetches,
            CASE 
                WHEN idx_scan > 0 THEN 'Used' 
                ELSE 'Unused' 
            END as usage_status
        FROM
            pg_stat_user_indexes
        WHERE
            schemaname NOT IN ('pg_catalog', 'information_schema')
            AND idx_scan = 0
        ORDER BY
            pg_relation_size(indexrelid) DESC;
        """
        
        try:
            with self.conn.cursor() as cur:
                try:
                    # Table bloat analysis
                    cur.execute(table_bloat_query)
                    self.data['bloat_analysis'] = [dict(zip([col[0] for col in cur.description], row)) 
                                                for row in cur.fetchall()]
                    logger.info(f"Collected bloat analysis for {len(self.data['bloat_analysis'])} tables")
                except Exception as e:
                    logger.warning(f"Could not collect table bloat analysis: {str(e)}")
                    self.data['bloat_analysis'] = []
        except Exception as e:
            logger.warning(f"Error in bloat analysis outer block: {str(e)}")
            self.data['bloat_analysis'] = []
            
        try:
            with self.conn.cursor() as cur:
                # Index bloat analysis (unused indexes)
                try:
                    cur.execute(index_bloat_query)
                    unused_indexes = [dict(zip([col[0] for col in cur.description], row)) 
                                   for row in cur.fetchall()]
                    self.data['unused_indexes'] = unused_indexes
                    logger.info(f"Found {len(unused_indexes)} unused indexes")
                except Exception as e:
                    logger.warning(f"Could not collect unused indexes analysis: {str(e)}")
                    self.data['unused_indexes'] = []
        except Exception as e:
            logger.warning(f"Error in unused indexes outer block: {str(e)}")
            self.data['unused_indexes'] = []
    
    def _collect_table_io_stats(self):
        """Collect I/O statistics for tables."""
        logger.info("Collecting table I/O statistics...")
        
        query = """
        SELECT
            schemaname as schema,
            relname as table_name,
            heap_blks_read as heap_read,
            heap_blks_hit as heap_hit,
            idx_blks_read as index_read,
            idx_blks_hit as index_hit,
            toast_blks_read as toast_read,
            toast_blks_hit as toast_hit,
            seq_scan,
            seq_tup_read,
            idx_scan,
            idx_tup_fetch,
            n_tup_ins as inserts,
            n_tup_upd as updates,
            n_tup_del as deletes,
            CASE 
                WHEN heap_blks_read + heap_blks_hit > 0 
                THEN round(100 * heap_blks_hit / (heap_blks_read + heap_blks_hit), 2) 
                ELSE NULL 
            END as heap_hit_ratio,
            CASE 
                WHEN idx_blks_read + idx_blks_hit > 0 
                THEN round(100 * idx_blks_hit / (idx_blks_read + idx_blks_hit), 2) 
                ELSE NULL 
            END as index_hit_ratio
        FROM
            pg_statio_user_tables
        JOIN
            pg_stat_user_tables USING (schemaname, relname)
        WHERE
            (heap_blks_read > 0 OR idx_blks_read > 0 OR seq_scan > 0 OR idx_scan > 0)
        ORDER BY
            (heap_blks_read + idx_blks_read) DESC
        LIMIT 50;
        """
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                self.data['table_io_stats'] = [dict(zip([col[0] for col in cur.description], row)) 
                                            for row in cur.fetchall()]
                
            logger.info(f"Collected I/O statistics for {len(self.data['table_io_stats'])} tables")
        except Exception as e:
            logger.warning(f"Could not collect table I/O statistics: {str(e)}")
            self.data['table_io_stats'] = []
    
    def _collect_index_usage(self):
        """Collect index usage statistics."""
        logger.info("Collecting index usage statistics...")
        
        query = """
        SELECT
            schemaname as schema,
            t.relname as table_name,
            indexrelname as index_name,
            pg_size_pretty(pg_relation_size(i.indexrelid)) as index_size,
            pg_relation_size(i.indexrelid) as size_bytes,
            idx_scan as scans,
            idx_tup_read as reads,
            idx_tup_fetch as fetches,
            CASE
                WHEN (seq_scan + idx_scan) = 0 THEN 0
                ELSE idx_scan::float / (seq_scan + idx_scan)
            END as index_scan_ratio,
            n_live_tup as live_tuples,
            n_dead_tup as dead_tuples
        FROM
            pg_stat_user_indexes i
        JOIN
            pg_stat_user_tables t ON i.schemaname = t.schemaname AND i.relname = t.relname
        WHERE
            t.idx_scan > 0
            AND i.schemaname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY
            idx_scan DESC,
            pg_relation_size(i.indexrelid) DESC
        LIMIT 50;
        """
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                self.data['index_usage'] = [dict(zip([col[0] for col in cur.description], row)) 
                                          for row in cur.fetchall()]
                
            logger.info(f"Collected usage statistics for {len(self.data['index_usage'])} indexes")
        except Exception as e:
            logger.warning(f"Could not collect index usage statistics: {str(e)}")
            self.data['index_usage'] = []

    def export_data(self, output_file=None):
        """Export collected data to a JSON file."""
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"pg_visualizer_{self.dbname}_{timestamp}.json"
            
        with open(output_file, 'w') as f:
            json.dump(self.data, f, indent=2, default=str)
        
        logger.info(f"Data exported to {output_file}")
        return output_file
    
    def create_visualizations(self, output_dir=None):
        """Create visualization charts and save them to the output directory."""
        if output_dir is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = f"pg_visualizer_{self.dbname}_{timestamp}"
            
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        logger.info(f"Creating visualizations in {output_dir}")
        
        # Create various visualizations
        self._visualize_table_sizes(output_dir)
        self._visualize_index_sizes(output_dir)
        self._visualize_table_growth(output_dir)
        self._visualize_relationships(output_dir)
        self._visualize_vacuum_status(output_dir)
        self._visualize_bloat(output_dir)
        self._visualize_io_stats(output_dir)
        self._visualize_performance_metrics(output_dir)
        
        # Create HTML report
        self._create_html_report(output_dir)
        
        logger.info(f"Visualizations created in {output_dir}")
        return output_dir
    
    def _visualize_table_sizes(self, output_dir):
        """Visualize table sizes."""
        if not self.data['tables']:
            return
            
        # Prepare data
        df = pd.DataFrame(self.data['tables'])
        
        # Filter for top N tables by size
        top_tables = df.sort_values('size_bytes', ascending=False).head(20)
        
        # Create figure
        plt.figure(figsize=(12, 8))
        sns.set_style("whitegrid")
        
        # Plot - Update to avoid deprecated warning with palette
        ax = sns.barplot(x='total_size', y='table_name', data=top_tables, hue='total_size', legend=False)
        
        # Add labels
        plt.title('Top 20 Tables by Size', fontsize=16)
        plt.xlabel('Table Size', fontsize=12)
        plt.ylabel('Table Name', fontsize=12)
        
        # Save figure
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'table_sizes.png'), dpi=300)
        plt.close()
        
        # Create interactive plotly figure for HTML
        fig = px.bar(
            top_tables, 
            x='size_bytes', 
            y='table_name',
            color='row_estimate',
            labels={
                'size_bytes': 'Size (bytes)',
                'table_name': 'Table Name',
                'row_estimate': 'Estimated Rows'
            },
            title='Top 20 Tables by Size',
            height=600
        )
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
        fig.write_html(os.path.join(output_dir, 'table_sizes.html'))
    
    def _visualize_index_sizes(self, output_dir):
        """Visualize index sizes."""
        if not self.data['indexes']:
            return
        
        # Prepare data - aggregate by index_name
        df = pd.DataFrame(self.data['indexes'])
        index_sizes = df.groupby(['schema', 'table_name', 'index_name', 'size_bytes', 'index_size']).size().reset_index(name='columns')
        
        # Filter for top N indexes by size
        top_indexes = index_sizes.sort_values('size_bytes', ascending=False).head(20)
        
        # Create figure
        plt.figure(figsize=(12, 8))
        sns.set_style("whitegrid")
        
        # Plot with hue parameter instead of palette
        ax = sns.barplot(x='index_size', y='index_name', data=top_indexes, hue='index_name', legend=False)
        
        # Add labels
        plt.title('Top 20 Indexes by Size', fontsize=16)
        plt.xlabel('Index Size', fontsize=12)
        plt.ylabel('Index Name', fontsize=12)
        
        # Save figure
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'index_sizes.png'), dpi=300)
        plt.close()
        
        # Create interactive plotly figure for HTML
        fig = px.bar(
            top_indexes, 
            x='size_bytes', 
            y='index_name',
            color='table_name',
            labels={
                'size_bytes': 'Size (bytes)',
                'index_name': 'Index Name',
                'table_name': 'Table Name'
            },
            title='Top 20 Indexes by Size',
            height=600
        )
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
        fig.write_html(os.path.join(output_dir, 'index_sizes.html'))
        
    def _visualize_table_growth(self, output_dir):
        """Visualize table growth based on available metrics."""
        if not self.data['vacuum_status']:
            return
            
        # We don't have historical data, but we can visualize current state 
        # of live vs dead tuples as an indicator of growth
        df = pd.DataFrame(self.data['vacuum_status'])
        
        # Filter for top N tables by total tuples
        df['total_tuples'] = df['live_tuples'] + df['dead_tuples']
        top_tables = df.sort_values('total_tuples', ascending=False).head(15)
        
        # Prepare data for stacked bar chart
        data = []
        for _, row in top_tables.iterrows():
            data.append({
                'table_name': row['table_name'],
                'tuple_type': 'Live Tuples',
                'count': row['live_tuples']
            })
            data.append({
                'table_name': row['table_name'],
                'tuple_type': 'Dead Tuples',
                'count': row['dead_tuples']
            })
        
        plot_df = pd.DataFrame(data)
        
        # Create figure
        fig = px.bar(
            plot_df,
            x='table_name',
            y='count',
            color='tuple_type',
            title='Live vs Dead Tuples in Top Tables',
            labels={
                'count': 'Number of Tuples',
                'table_name': 'Table Name',
                'tuple_type': 'Tuple Type'
            },
            height=600,
            barmode='stack'
        )
        
        fig.update_layout(xaxis={'categoryorder': 'total descending'})
        fig.write_html(os.path.join(output_dir, 'table_tuples.html'))
        
    def _visualize_relationships(self, output_dir):
        """Visualize table relationships as a network graph."""
        if not self.data['relationships']:
            return
            
        # Create a network graph
        G = nx.DiGraph()
        
        # Add nodes and edges
        for rel in self.data['relationships']:
            source = f"{rel['source_schema']}.{rel['source_table']}"
            target = f"{rel['target_schema']}.{rel['target_table']}"
            
            # Add nodes if they don't exist
            if not G.has_node(source):
                G.add_node(source)
            if not G.has_node(target):
                G.add_node(target)
                
            # Add edge
            G.add_edge(
                source, 
                target, 
                label=f"{rel['source_column']} -> {rel['target_column']}"
            )
        
        # Position nodes using force-directed layout - do this regardless of graph size
        pos = nx.spring_layout(G, k=0.15, iterations=50)
        
        # Draw the graph if it's not too large
        if len(G.nodes) <= 50:  # Only create static visualization if not too many tables
            plt.figure(figsize=(14, 10))
            
            # Draw nodes
            nx.draw_networkx_nodes(G, pos, node_size=700, node_color="skyblue", alpha=0.8)
            
            # Draw edges
            nx.draw_networkx_edges(G, pos, width=1.0, alpha=0.5, arrowsize=20)
            
            # Draw labels
            nx.draw_networkx_labels(G, pos, font_size=8, font_weight="bold")
            
            plt.title('Database Relationship Diagram', fontsize=16)
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, 'relationships.png'), dpi=300, bbox_inches='tight')
            plt.close()
        
        # Create an interactive network graph using Plotly - check if we have any nodes
        if len(G.nodes) == 0:
            logger.warning("No relationship data to visualize")
            return
            
        # Create edges for the plotly graph
        edge_x = []
        edge_y = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=0.5, color='#888'),
            hoverinfo='none',
            mode='lines')
            
        node_x = []
        node_y = []
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            hoverinfo='text',
            text=[node.split('.')[-1] for node in G.nodes()],
            textposition="top center",
            marker=dict(
                showscale=True,
                colorscale='YlGnBu',
                size=10,
                colorbar=dict(
                    thickness=15,
                    title=dict(
                        text='Node Connections',
                        side='right'
                    ),
                    xanchor='left'
                ),
                line_width=2))
                
        # Color nodes by number of connections
        node_adjacencies = []
        for node in G.nodes():
            node_adjacencies.append(len(list(G.neighbors(node))))
            
        node_trace.marker.color = node_adjacencies
        
        # Create the figure
        fig = go.Figure(data=[edge_trace, node_trace],
                     layout=go.Layout(
                        title='Database Relationship Diagram',
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20,l=5,r=5,t=40),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                        )
        
        fig.write_html(os.path.join(output_dir, 'relationships_interactive.html'))
        
    def _visualize_vacuum_status(self, output_dir):
        """Visualize vacuum status."""
        if not self.data['vacuum_status']:
            return
            
        df = pd.DataFrame(self.data['vacuum_status'])
        
        # Sort by dead_tuple_pct descending
        top_tables = df.sort_values('dead_tuple_pct', ascending=False).head(20)
        
        # Create figure
        fig = px.bar(
            top_tables,
            x='table_name',
            y='dead_tuple_pct',
            color='dead_tuple_pct',
            color_continuous_scale='Reds',
            title='Tables with Highest Dead Tuple Percentage',
            labels={
                'dead_tuple_pct': 'Dead Tuple %',
                'table_name': 'Table Name'
            },
            height=600
        )
        
        fig.update_layout(xaxis={'categoryorder': 'total descending'})
        fig.add_hline(y=20, line_dash="dash", line_color="red", 
                    annotation_text="Vacuum Threshold", 
                    annotation_position="top right")
        
        fig.write_html(os.path.join(output_dir, 'vacuum_status.html'))
        
    def _visualize_bloat(self, output_dir):
        """Visualize table and index bloat."""
        if not self.data['bloat_analysis']:
            return
            
        df = pd.DataFrame(self.data['bloat_analysis'])
        
        # Create figure
        fig = px.scatter(
            df,
            x='table_size',
            y='bloat_pct',
            size='bloat_mb',
            color='bloat_pct',
            hover_name='table_name',
            color_continuous_scale='RdYlGn_r',
            title='Table Bloat Analysis',
            labels={
                'table_size': 'Table Size',
                'bloat_pct': 'Bloat Percentage',
                'bloat_mb': 'Bloat Size (MB)'
            },
            height=600
        )
        
        fig.update_layout(
            xaxis_title="Table Size (bytes)",
            yaxis_title="Bloat (%)",
        )
        
        fig.write_html(os.path.join(output_dir, 'bloat_analysis.html'))
        
        # If we have unused indexes data
        if 'unused_indexes' in self.data and self.data['unused_indexes']:
            unused_df = pd.DataFrame(self.data['unused_indexes'])
            
            fig2 = px.bar(
                unused_df.sort_values('size_bytes', ascending=False).head(20),
                x='index_name',
                y='size_bytes',
                color='table_name',
                title='Top 20 Unused Indexes by Size',
                labels={
                    'index_name': 'Index Name',
                    'size_bytes': 'Size (bytes)',
                    'table_name': 'Table Name'
                },
                height=600
            )
            
            fig2.update_layout(xaxis={'categoryorder': 'total descending'})
            fig2.write_html(os.path.join(output_dir, 'unused_indexes.html'))
        
    def _visualize_io_stats(self, output_dir):
        """Visualize I/O statistics."""
        if not self.data['table_io_stats']:
            return
            
        df = pd.DataFrame(self.data['table_io_stats'])
        
        # Handle None values in index_hit_ratio
        df['index_hit_ratio_filled'] = df['index_hit_ratio'].fillna(0)
        
        # Create bubble chart for read operations
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("Sequential vs Index Scans", "Cache Hit Ratios"),
            specs=[[{"type": "scatter"}, {"type": "bar"}]]
        )
        
        # Add sequential vs index scan data
        fig.add_trace(
            go.Scatter(
                x=df['seq_scan'],
                y=df['idx_scan'],
                mode='markers',
                marker=dict(
                    size=df['seq_tup_read'] / 1000,  # Scale for visibility
                    sizemode='area',
                    sizeref=2.*max(df['seq_tup_read']/1000)/(40.**2),
                    color=df['index_hit_ratio_filled'],
                    colorscale='Viridis',
                    colorbar=dict(title=dict(text='Index Hit Ratio', side='right')),
                    showscale=True
                ),
                text=df['table_name'],
                hovertemplate=
                '<b>%{text}</b><br><br>' +
                'Sequential scans: %{x}<br>' +
                'Index scans: %{y}<br>' +
                'Sequential tuples read: %{marker.size}<br>' +
                'Index hit ratio: %{marker.color:.2f}%<br>',
            ),
            row=1, col=1
        )
        
        # Add cache hit ratio data
        # First filter out None values and create a new dataframe
        top_tables = df.dropna(subset=['heap_hit_ratio', 'index_hit_ratio']).sort_values('heap_hit_ratio', ascending=True).head(10)
        
        # Only proceed if we have data
        if not top_tables.empty:
            fig.add_trace(
                go.Bar(
                    x=top_tables['table_name'],
                    y=top_tables['heap_hit_ratio'],
                    name='Heap Hit Ratio',
                    marker_color='blue'
                ),
                row=1, col=2
            )
            
            fig.add_trace(
                go.Bar(
                    x=top_tables['table_name'],
                    y=top_tables['index_hit_ratio'],
                    name='Index Hit Ratio',
                    marker_color='green'
                ),
                row=1, col=2
            )
        
        # Update layout
        fig.update_layout(
            title='Table I/O Statistics',
            height=600,
            xaxis=dict(title='Sequential Scans'),
            yaxis=dict(title='Index Scans'),
            xaxis2=dict(title='Table'),
            yaxis2=dict(title='Hit Ratio (%)'),
            showlegend=True
        )
        
        fig.write_html(os.path.join(output_dir, 'io_stats.html'))
        
    def _visualize_performance_metrics(self, output_dir):
        """Visualize performance metrics."""
        # Database activity overview
        if 'connection_stats' in self.data['performance']:
            conn_stats = self.data['performance']['connection_stats']
            
            # Create pie chart for operation types
            labels = ['SELECT', 'INSERT', 'UPDATE', 'DELETE']
            values = [
                conn_stats.get('tup_returned', 0), 
                conn_stats.get('tup_inserted', 0),
                conn_stats.get('tup_updated', 0),
                conn_stats.get('tup_deleted', 0)
            ]
            
            fig = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=.3
            )])
            
            fig.update_layout(title='Database Operation Types')
            fig.write_html(os.path.join(output_dir, 'operation_types.html'))
            
            # Create bar chart for commits vs rollbacks
            if 'commits' in conn_stats and 'rollbacks' in conn_stats:
                commit_data = [
                    {'Type': 'Commits', 'Count': conn_stats['commits']},
                    {'Type': 'Rollbacks', 'Count': conn_stats['rollbacks']}
                ]
                
                fig2 = px.bar(
                    commit_data,
                    x='Type',
                    y='Count',
                    color='Type',
                    title='Transactions: Commits vs Rollbacks',
                    height=400
                )
                
                fig2.write_html(os.path.join(output_dir, 'transactions.html'))
        
        # Query performance visualization
        if 'query_stats' in self.data['performance'] and self.data['performance']['query_stats']:
            query_df = pd.DataFrame(self.data['performance']['query_stats'])
            
            # Create figure for top queries by execution time
            fig3 = px.bar(
                query_df.head(10),
                x='total_time',
                y=query_df.head(10).index,
                color='mean_time',
                orientation='h',
                title='Top 10 Queries by Total Execution Time',
                labels={
                    'total_time': 'Total Execution Time (ms)',
                    'y': 'Query #',
                    'mean_time': 'Mean Execution Time (ms)'
                },
                height=600,
                color_continuous_scale='Viridis'
            )
            
            # Add query text as hover information
            query_texts = []
            for query in query_df.head(10)['query']:
                # Truncate long queries for display
                if len(query) > 100:
                    query_texts.append(query[:100] + '...')
                else:
                    query_texts.append(query)
                    
            fig3.update_traces(
                hovertemplate='<b>Total time</b>: %{x} ms<br>' +
                              '<b>Mean time</b>: %{marker.color} ms<br>' +
                              '<b>Query</b>: %{customdata}',
                customdata=query_texts
            )
            
            fig3.write_html(os.path.join(output_dir, 'query_performance.html'))
            
    def _create_html_report(self, output_dir):
        """Create a comprehensive HTML report with all visualizations."""
        html_path = os.path.join(output_dir, 'index.html')
        
        # Get list of all HTML files in output_dir
        html_files = [f for f in os.listdir(output_dir) if f.endswith('.html') and f != 'index.html']
        
        # Create HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>PostgreSQL Database Analysis Report</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                header {{
                    background-color: #2c3e50;
                    color: white;
                    padding: 20px;
                    text-align: center;
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                }}
                .summary-card {{
                    background-color: white;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    padding: 20px;
                    margin-bottom: 20px;
                }}
                .dashboard {{
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
                    grid-gap: 20px;
                    margin-top: 20px;
                }}
                .dashboard-item {{
                    background-color: white;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    padding: 15px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                th, td {{
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
                iframe {{
                    width: 100%;
                    height: 450px;
                    border: none;
                }}
                .tabs {{
                    display: flex;
                    margin-bottom: 20px;
                }}
                .tab {{
                    padding: 10px 20px;
                    cursor: pointer;
                    background-color: #f2f2f2;
                    margin-right: 5px;
                    border-radius: 5px 5px 0 0;
                }}
                .tab.active {{
                    background-color: #2c3e50;
                    color: white;
                }}
                .tab-content {{
                    display: none;
                }}
                .tab-content.active {{
                    display: block;
                }}
                .warning {{
                    background-color: #ffe6e6;
                    border-left: 5px solid #ff6666;
                    padding: 10px;
                    margin-bottom: 10px;
                }}
                .success {{
                    background-color: #e6ffe6;
                    border-left: 5px solid #66ff66;
                    padding: 10px;
                    margin-bottom: 10px;
                }}
            </style>
        </head>
        <body>
            <header>
                <h1>PostgreSQL Database Analysis Report</h1>
                <p>Database: {self.dbname} | Server: {self.host}:{self.port} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </header>
            
            <div class="container">
                <div class="summary-card">
                    <h2>Database Summary</h2>
                    <table>
                        <tr>
                            <th>Database Size</th>
                            <td>{self.data['performance'].get('db_size', {}).get('db_size', 'Unknown')}</td>
                        </tr>
                        <tr>
                            <th>Tables</th>
                            <td>{len(self.data['tables'])}</td>
                        </tr>
                        <tr>
                            <th>CStore Tables</th>
                            <td>{len(self.data['cstore_tables'])}</td>
                        </tr>
                        <tr>
                            <th>Indexes</th>
                            <td>{len(self.data['indexes'])}</td>
                        </tr>
                        <tr>
                            <th>Cache Hit Ratio</th>
                            <td>{self.data['performance'].get('connection_stats', {}).get('cache_hit_ratio', 'Unknown')}%</td>
                        </tr>
                    </table>
                </div>
                
                <div class="tabs">
                    <div class="tab active" onclick="openTab(event, 'overview')">Overview</div>
                    <div class="tab" onclick="openTab(event, 'performance')">Performance</div>
                    <div class="tab" onclick="openTab(event, 'tables')">Tables</div>
                    <div class="tab" onclick="openTab(event, 'indexes')">Indexes</div>
                    <div class="tab" onclick="openTab(event, 'issues')">Issues</div>
                </div>
                
                <div id="overview" class="tab-content active">
                    <h2>Database Overview</h2>
                    <div class="dashboard">
        """
        
        # Add overview visualizations
        if 'table_sizes.html' in html_files:
            html_content += """
            <div class="dashboard-item">
                <h3>Table Sizes</h3>
                <iframe src="table_sizes.html"></iframe>
            </div>
            """
            
        if 'relationships_interactive.html' in html_files:
            html_content += """
            <div class="dashboard-item">
                <h3>Table Relationships</h3>
                <iframe src="relationships_interactive.html"></iframe>
            </div>
            """
            
        if 'operation_types.html' in html_files:
            html_content += """
            <div class="dashboard-item">
                <h3>Operation Types</h3>
                <iframe src="operation_types.html"></iframe>
            </div>
            """
            
        html_content += """
                    </div>
                </div>
                
                <div id="performance" class="tab-content">
                    <h2>Performance Analysis</h2>
                    <div class="dashboard">
        """
        
        # Add performance visualizations
        if 'io_stats.html' in html_files:
            html_content += """
            <div class="dashboard-item">
                <h3>I/O Statistics</h3>
                <iframe src="io_stats.html"></iframe>
            </div>
            """
            
        if 'query_performance.html' in html_files:
            html_content += """
            <div class="dashboard-item">
                <h3>Query Performance</h3>
                <iframe src="query_performance.html"></iframe>
            </div>
            """
            
        if 'transactions.html' in html_files:
            html_content += """
            <div class="dashboard-item">
                <h3>Transactions</h3>
                <iframe src="transactions.html"></iframe>
            </div>
            """
            
        html_content += """
                    </div>
                </div>
                
                <div id="tables" class="tab-content">
                    <h2>Table Analysis</h2>
                    <div class="dashboard">
        """
        
        # Add table visualizations
        if 'table_tuples.html' in html_files:
            html_content += """
            <div class="dashboard-item">
                <h3>Table Tuples</h3>
                <iframe src="table_tuples.html"></iframe>
            </div>
            """
            
        if 'vacuum_status.html' in html_files:
            html_content += """
            <div class="dashboard-item">
                <h3>Vacuum Status</h3>
                <iframe src="vacuum_status.html"></iframe>
            </div>
            """
            
        if 'bloat_analysis.html' in html_files:
            html_content += """
            <div class="dashboard-item">
                <h3>Table Bloat</h3>
                <iframe src="bloat_analysis.html"></iframe>
            </div>
            """
            
        html_content += """
                    </div>
                </div>
                
                <div id="indexes" class="tab-content">
                    <h2>Index Analysis</h2>
                    <div class="dashboard">
        """
        
        # Add index visualizations
        if 'index_sizes.html' in html_files:
            html_content += """
            <div class="dashboard-item">
                <h3>Index Sizes</h3>
                <iframe src="index_sizes.html"></iframe>
            </div>
            """
            
        if 'unused_indexes.html' in html_files:
            html_content += """
            <div class="dashboard-item">
                <h3>Unused Indexes</h3>
                <iframe src="unused_indexes.html"></iframe>
            </div>
            """
            
        html_content += """
                    </div>
                </div>
                
                <div id="issues" class="tab-content">
                    <h2>Potential Issues</h2>
        """
        
        # Add issues section
        issues_found = False
        
        # Check for bloated tables
        if self.data['bloat_analysis']:
            bloated_tables = [t for t in self.data['bloat_analysis'] if t['bloat_pct'] > 50]
            if bloated_tables:
                issues_found = True
                html_content += """
                <div class="warning">
                    <h3>Tables with High Bloat</h3>
                    <p>The following tables have over 50% bloat and should be considered for VACUUM FULL or reindexing:</p>
                    <ul>
                """
                for table in bloated_tables[:10]:  # Show top 10 most bloated
                    html_content += f"""
                    <li><strong>{table['schema']}.{table['table_name']}</strong>: {table['bloat_pct']}% bloat ({table['bloat_mb']} MB wasted)</li>
                    """
                
                html_content += """
                    </ul>
                </div>
                """
        
        # Check for unused indexes
        if 'unused_indexes' in self.data and self.data['unused_indexes']:
            large_unused_indexes = sorted(
                [idx for idx in self.data['unused_indexes'] if idx['size_bytes'] > 10*1024*1024],  # >10MB
                key=lambda x: x['size_bytes'],
                reverse=True
            )
            
            if large_unused_indexes:
                issues_found = True
                html_content += """
                <div class="warning">
                    <h3>Large Unused Indexes</h3>
                    <p>The following large indexes have never been used and are candidates for removal:</p>
                    <ul>
                """
                for idx in large_unused_indexes[:10]:  # Show top 10 largest unused
                    html_content += f"""
                    <li><strong>{idx['schema']}.{idx['index_name']}</strong> on {idx['table_name']}: {idx['index_size']}</li>
                    """
                
                html_content += """
                    </ul>
                </div>
                """
        
        # Check for tables with low cache hit ratio
        if self.data['table_io_stats']:
            low_cache_tables = [
                t for t in self.data['table_io_stats'] 
                if t['heap_hit_ratio'] is not None and t['heap_hit_ratio'] < 80
                and t['heap_read'] > 1000  # Only consider tables with significant reads
            ]
            
            if low_cache_tables:
                issues_found = True
                html_content += """
                <div class="warning">
                    <h3>Tables with Poor Cache Performance</h3>
                    <p>The following tables have a cache hit ratio below 80% and may need attention:</p>
                    <ul>
                """
                for table in sorted(low_cache_tables, key=lambda x: x['heap_hit_ratio'])[:10]:
                    html_content += f"""
                    <li><strong>{table['schema']}.{table['table_name']}</strong>: {table['heap_hit_ratio']}% cache hit ratio</li>
                    """
                
                html_content += """
                    </ul>
                </div>
                """
                
        # Check for tables with high dead tuples
        if self.data['vacuum_status']:
            high_dead_tuples = [
                t for t in self.data['vacuum_status'] 
                if t['dead_tuple_pct'] > 20 and t['live_tuples'] > 10000  # Only significant tables
            ]
            
            if high_dead_tuples:
                issues_found = True
                html_content += """
                <div class="warning">
                    <h3>Tables Needing VACUUM</h3>
                    <p>The following tables have more than 20% dead tuples and should be vacuumed:</p>
                    <ul>
                """
                for table in sorted(high_dead_tuples, key=lambda x: x['dead_tuple_pct'], reverse=True)[:10]:
                    html_content += f"""
                    <li><strong>{table['schema']}.{table['table_name']}</strong>: {table['dead_tuple_pct']}% dead tuples 
                    (last vacuumed: {table['last_vacuum'] or 'never'})</li>
                    """
                
                html_content += """
                    </ul>
                </div>
                """
        
        # Check for long-standing locks
        if self.data['locks']:
            long_locks = [l for l in self.data['locks'] if l['query_duration_sec'] > 60]  # Locks > 1 minute
            
            if long_locks:
                issues_found = True
                html_content += """
                <div class="warning">
                    <h3>Long-Standing Locks</h3>
                    <p>The following locks have been active for more than 1 minute and may be causing blocking issues:</p>
                    <ul>
                """
                for lock in sorted(long_locks, key=lambda x: x['query_duration_sec'], reverse=True)[:10]:
                    html_content += f"""
                    <li><strong>{lock['schema']}.{lock['table_name']}</strong>: {lock['mode']} lock by PID {lock['pid']} 
                    for {lock['query_duration_sec']} seconds</li>
                    """
                
                html_content += """
                    </ul>
                </div>
                """
                
        if not issues_found:
            html_content += """
            <div class="success">
                <h3>No Critical Issues Found</h3>
                <p>No significant database issues were detected in this analysis. Continue monitoring regularly for optimal performance.</p>
            </div>
            """
            
        # Close the HTML
        html_content += """
                </div>
            </div>
            
            <script>
            function openTab(evt, tabName) {
                // Declare all variables
                var i, tabContent, tabLinks;
            
                // Get all elements with class="tab-content" and hide them
                tabContent = document.getElementsByClassName("tab-content");
                for (i = 0; i < tabContent.length; i++) {
                    tabContent[i].style.display = "none";
                }
            
                // Get all elements with class="tab" and remove the class "active"
                tabLinks = document.getElementsByClassName("tab");
                for (i = 0; i < tabLinks.length; i++) {
                    tabLinks[i].className = tabLinks[i].className.replace(" active", "");
                }
            
                // Show the current tab, and add an "active" class to the button that opened the tab
                document.getElementById(tabName).style.display = "block";
                evt.currentTarget.className += " active";
            }
            </script>
        </body>
        </html>
        """
        
        # Write HTML to file
        with open(html_path, 'w') as f:
            f.write(html_content)
            
        logger.info(f"Created HTML report at {html_path}")
        
    def launch_dashboard(self, output_dir):
        """Launch a Dash web application to show database visualizations interactively."""
        app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
        
        # Define app layout
        app.layout = html.Div([
            html.H1(f"PostgreSQL Database Monitor: {self.dbname}"),
            html.Hr(),
            
            dbc.Tabs([
                dbc.Tab(label="Overview", children=[
                    html.Div([
                        html.H3("Database Summary"),
                        html.Div(id="summary-stats"),
                        
                        html.H3("Table Sizes"),
                        dcc.Graph(id="table-sizes-graph")
                    ])
                ]),
                
                dbc.Tab(label="Performance", children=[
                    html.Div([
                        html.H3("IO Statistics"),
                        dcc.Graph(id="io-stats-graph"),
                        
                        html.H3("Query Performance"),
                        dcc.Graph(id="query-performance-graph")
                    ])
                ]),
                
                dbc.Tab(label="Health", children=[
                    html.Div([
                        html.H3("Vacuum Status"),
                        dcc.Graph(id="vacuum-status-graph"),
                        
                        html.H3("Bloat Analysis"),
                        dcc.Graph(id="bloat-analysis-graph")
                    ])
                ]),
                
                dbc.Tab(label="Issues", children=[
                    html.Div(id="issues-panel")
                ])
            ])
        ])
        
        # Define callbacks to update dashboard
        @app.callback(
            Output("summary-stats", "children"),
            Input("summary-stats", "id")
        )
        def update_summary():
            return html.Div([
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Database Size", className="card-title"),
                        html.P(
                            self.data['performance'].get('db_size', {}).get('db_size', 'Unknown'),
                            className="card-text"
                        )
                    ])
                ),
                
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Tables", className="card-title"),
                        html.P(
                            f"{len(self.data['tables'])} tables, {len(self.data['cstore_tables'])} cstore tables",
                            className="card-text"
                        )
                    ])
                ),
                
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Cache Hit Ratio", className="card-title"),
                        html.P(
                            f"{self.data['performance'].get('connection_stats', {}).get('cache_hit_ratio', 'Unknown')}%",
                            className="card-text"
                        )
                    ])
                )
            ])
        
        @app.callback(
            Output("table-sizes-graph", "figure"),
            Input("table-sizes-graph", "id")
        )
        def update_table_sizes():
            if not self.data['tables']:
                return {}
                
            df = pd.DataFrame(self.data['tables'])
            top_tables = df.sort_values('size_bytes', ascending=False).head(20)
            
            fig = px.bar(
                top_tables, 
                x='size_bytes', 
                y='table_name',
                color='row_estimate',
                labels={
                    'size_bytes': 'Size (bytes)',
                    'table_name': 'Table Name',
                    'row_estimate': 'Estimated Rows'
                },
                title='Top 20 Tables by Size'
            )
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            return fig
        
        @app.callback(
            Output("io-stats-graph", "figure"),
            Input("io-stats-graph", "id")
        )
        def update_io_stats():
            if not self.data['table_io_stats']:
                return {}
                
            df = pd.DataFrame(self.data['table_io_stats'])
            
            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=("Sequential vs Index Scans", "Cache Hit Ratios")
            )
            
            fig.add_trace(
                go.Scatter(
                    x=df['seq_scan'],
                    y=df['idx_scan'],
                    mode='markers',
                    marker=dict(
                        size=df['seq_tup_read'] / 1000,
                        color=df['index_hit_ratio'],
                        colorscale='Viridis',
                        showscale=True
                    ),
                    text=df['table_name']
                ),
                row=1, col=1
            )
            
            top_tables = df.sort_values('heap_hit_ratio', ascending=True).head(10)
            
            fig.add_trace(
                go.Bar(
                    x=top_tables['table_name'],
                    y=top_tables['heap_hit_ratio'],
                    name='Heap Hit Ratio'
                ),
                row=1, col=2
            )
            
            fig.add_trace(
                go.Bar(
                    x=top_tables['table_name'],
                    y=top_tables['index_hit_ratio'],
                    name='Index Hit Ratio'
                ),
                row=1, col=2
            )
            
            fig.update_layout(title='Table I/O Statistics')
            return fig
            
        @app.callback(
            Output("vacuum-status-graph", "figure"),
            Input("vacuum-status-graph", "id")
        )
        def update_vacuum_status():
            if not self.data['vacuum_status']:
                return {}
                
            df = pd.DataFrame(self.data['vacuum_status'])
            top_tables = df.sort_values('dead_tuple_pct', ascending=False).head(20)
            
            fig = px.bar(
                top_tables,
                x='table_name',
                y='dead_tuple_pct',
                color='dead_tuple_pct',
                color_continuous_scale='Reds',
                title='Tables with Highest Dead Tuple Percentage'
            )
            
            fig.update_layout(xaxis={'categoryorder': 'total descending'})
            fig.add_hline(y=20, line_dash="dash", line_color="red")
            
            return fig
            
        @app.callback(
            Output("bloat-analysis-graph", "figure"),
            Input("bloat-analysis-graph", "id")
        )
        def update_bloat_analysis():
            if not self.data['bloat_analysis']:
                return {}
                
            df = pd.DataFrame(self.data['bloat_analysis'])
            
            fig = px.scatter(
                df,
                x='table_size',
                y='bloat_pct',
                size='bloat_mb',
                color='bloat_pct',
                hover_name='table_name',
                color_continuous_scale='RdYlGn_r',
                title='Table Bloat Analysis'
            )
            
            return fig
            
        @app.callback(
            Output("issues-panel", "children"),
            Input("issues-panel", "id")
        )
        def update_issues():
            issues = []
            
            # Check for bloated tables
            if self.data['bloat_analysis']:
                bloated_tables = [t for t in self.data['bloat_analysis'] if t['bloat_pct'] > 50]
                if bloated_tables:
                    issues.append(
                        dbc.Alert(
                            [
                                html.H4("Tables with High Bloat", className="alert-heading"),
                                html.P("The following tables have over 50% bloat and should be considered for VACUUM FULL:"),
                                html.Ul([
                                    html.Li(f"{t['schema']}.{t['table_name']}: {t['bloat_pct']}% bloat ({t['bloat_mb']} MB wasted)")
                                    for t in bloated_tables[:10]
                                ])
                            ],
                            color="danger"
                        )
                    )
            
            # Add more issue checks here
            
            if not issues:
                issues.append(
                    dbc.Alert(
                        [
                            html.H4("No Critical Issues Found", className="alert-heading"),
                            html.P("No significant database issues were detected in this analysis.")
                        ],
                        color="success"
                    )
                )
                
            return html.Div(issues)
        
        # Run the app
        logger.info(f"Launching interactive dashboard at http://127.0.0.1:8050")
        app.run_server(debug=True)


def main():
    """Main function to run the PostgreSQL database visualizer."""
    parser = argparse.ArgumentParser(description='PostgreSQL Database Visualizer')
    
    # Connection parameters
    parser.add_argument('--host', required=True, help='Database server hostname')
    parser.add_argument('--port', type=int, default=5432, help='Database server port')
    parser.add_argument('--dbname', required=True, help='Database name')
    parser.add_argument('--user', required=True, help='Database user')
    parser.add_argument('--password', help='Database password (optional, will prompt if not provided)')
    
    # SSL certificate parameters
    parser.add_argument('--cert', help='Path to client certificate file')
    parser.add_argument('--key', help='Path to client key file')
    parser.add_argument('--ca-cert', help='Path to CA certificate file')
    
    # Output parameters
    parser.add_argument('--output-dir', help='Output directory for visualizations')
    parser.add_argument('--export-json', help='Export data to JSON file')
    parser.add_argument('--dashboard', action='store_true', help='Launch interactive dashboard')
    
    args = parser.parse_args()
    
    # Get password if not provided
    password = args.password
    if password is None and not (args.cert and args.key):
        import getpass
        password = getpass.getpass('Database password: ')
    
    # Initialize visualizer
    visualizer = PostgresVisualizer(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=password,
        cert_path=args.cert,
        key_path=args.key,
        ca_cert_path=args.ca_cert
    )
    
    # Collect database information
    if not visualizer.collect_database_info():
        print("Failed to collect database information. Exiting.")
        return 1
    
    # Export data to JSON if requested
    if args.export_json:
        json_file = visualizer.export_data(args.export_json)
        print(f"Data exported to {json_file}")
    
    # Create visualizations
    output_dir = visualizer.create_visualizations(args.output_dir)
    print(f"Visualizations created in {output_dir}")
    
    # Launch dashboard if requested
    if args.dashboard:
        visualizer.launch_dashboard(output_dir)
    
    # Close connection
    visualizer.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
