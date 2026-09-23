from urllib import response
import requests
import json
import pprint

hops_choise = input('Please enter your hops choise: ')

#url = f"https://api.punkapi.com/v2/beers?hops={hops_choise}"4 
url = "https://api.punkapi.com/v2/beers"
#params = {"q":"Darth Vader"}

#response = requests.get(url)
response = requests.get(url)

if response.status_code == 200:
    #print(response.text)
    data = json.loads(response.text)

    beer_list = []
    file = open("punk-beers.txt", "w+")

    for beer in data:


        name = beer['name']
        ibu = beer['ibu']
        tagline = beer['tagline']
        abv = beer['abv']
        #hops = beer['hops']

        beer_item = {
            'name': name,
            'ibu': ibu,
            'tagline': tagline,
            'abv': abv,
         #   'hops': hops
        }
        beer_list.append(beer_item)
        file.write(str(beer_item) +  "\n")

        #print(beer_item)

    
    file.close()  
    #print(beer_list)
    #name = data[0]['name']
    #ibu = data[0]['ibu']
    #gender = data['gender']
    #eye_color = data['eye_color']
    #hair_color = data['hair_color']
    
    #print("Beer " + name + " o IBU " + str(ibu))

        #print("Beer " + name + " o IBU " + str(ibu), tagline)

    #pprint.pprint(data)

else:
    print(f"Error {response.status_code}")
