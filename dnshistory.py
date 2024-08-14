import requests
import re
import validators
import sys

# Take user domain input
domain = input("Enter a domain name: ")
if validators.domain(domain):
    print("Running search...")
else:
    print("Not a valid domain name")
    sys.exit()

# Make request for domain
r = requests.get('https://dnsarchive.net/domain/' + domain)
results = str(r.content)
ip_list = re.findall(r"(\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b)|(\d+-\d+-\d+)", results)

# Build array by date
display_data_temp = []
temp_row = []
for x in ip_list:
    x = ''.join(x)
    x = x.replace('(', '')
    x.replace(')', '')
    if re.search(r"(\d{4}-\d{1,2}-\d{1,2})", x):
        temp_row = []
        temp_row.append(x)
    if re.search(r"(\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b)", x):
        if x in temp_row:
            pass
        else:
            temp_row.append(x)
    display_data_temp.append(temp_row)

# Clean and sort array
display_data_temp = [i for n, i in enumerate(display_data_temp) if i not in display_data_temp[:n]]
display_data = display_data_temp
display_data[0].insert(0, 'Latest    ')
display_data.sort(reverse=True)

# Turn array into display by columns
print('\n'.join([' | '.join(['{:4}'.format(item) for item in row]) 
      for row in display_data]))



