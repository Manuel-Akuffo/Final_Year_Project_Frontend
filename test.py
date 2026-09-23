import requests

url = "http://127.0.0.1:5000/predict"

data = {
    "age": 25,
    "heart_rate": 75,
    "blood_pressure": 101,
}

response = requests.post(url, json=data)
print(response.json())