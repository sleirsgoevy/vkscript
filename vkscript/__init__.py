from vkscript.lexer import VKSyntaxError
from vkscript.compiler import compile
from vkscript.runtime import exec as _exec, VKRuntimeError

def exec(*pargs, **args):
    if isinstance(pargs[0], str): pargs = (compile(pargs[0]),)+pargs[1:]
    return _exec(*pargs, **args)
