# Simple tunnel using Python's sshtunnel

from sshtunnel import SSHTunnelForwarder

server = SSHTunnelForwarder(
	'10.0.140.94',
	ssh_username='plixer',
	ssh_password='root',
	remote_bind_address=('127.0.0.1', 7777)
)
server.start()

print(server.local_bind_port, "This is the binding port")

server.stop()
