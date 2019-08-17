import vk.api, json, os, sys, time

api = vk.api.API(vk.api.Session(access_token=os.environ['API_TOKEN']), v='5.78')

code = open(sys.argv[1]).read()

print(api.execute(code=code))
