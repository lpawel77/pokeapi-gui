import http.client


#https://swapi.dev/api/people
conn = http.client.HTTPSConnection("swapi.dev")

conn.request("GET", "/api/people")

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
