import vk.api, json, os, sys, time

api = vk.api.API(vk.api.Session(access_token=os.environ['API_TOKEN']), v='5.78')

code = open(sys.argv[1]).read()

low = -9935
high = 10001

varname = '__'+os.urandom(64).hex()

def gen_cnt(i):
    if i == 0: return ''
    elif i == 1: return 'var '+varname+'=0;\n'
    elif i < 50:
        return '~'*(i-2)+'1;'
    elif (i - 7) % 10 == 1:
        return gen_cnt(i-1).replace('=0', '=~-1', 1)
    else:
        return 'var '+varname+'=0;\nwhile('+varname+'<'+str((i-7)//10)+')'+varname+'='+varname+'+1;\n'+gen_cnt((i-7)%10)

while high - low > 1:
    mid = (high + low) // 2
    if mid < 0:
        low = 1
        continue
    print(mid, '?', file=sys.stderr)
    code2 = gen_cnt(10000-mid)+'1;'+code
    try: api.execute(code=code2)
    except vk.exceptions.VkAPIError: low = mid
    else: high = mid
    time.sleep(0.4)

print(low, '!', file=sys.stderr)
print(high)
