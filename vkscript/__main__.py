from . import exec as vk_exec
import sys

print(vk_exec(open(sys.argv[1]).read()))
