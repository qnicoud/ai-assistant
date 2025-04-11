import ollama

for model in ollama.list()["models"]:
    print(model["model"].split(':')[0])

