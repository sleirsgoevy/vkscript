import vkscript.parser as parser, vkscript.lexer as lexer

def precompile(code):
    if not isinstance(code, parser.CodeBlock):
        code = parser.parse(code)
    ans = []
    stack = [code.compile(False)]
    stack[0].reverse()
    while True:
        while stack and not stack[-1]:
            stack.pop()
        if not stack: break
        instr = stack[-1].pop()
        if instr[0] == '.recur':
#           print(instr[1])
            stack.append(instr[1].compile())
            stack[-1].reverse()
        else:
            if isinstance(instr, str): instr = (instr,)
            ans.append(instr)
    return ans

def compile(code):
    code = precompile(code)
    ans = []
    comefrom_stack = []
    goto_stack = []
    cgoto_stack = []
    varnames_stack = [({'Args': 0, 0: 1}, set('Args'))]
    for cmd, *args in code:
        if cmd == '.comefrom':
            comefrom_stack.append(len(ans))
        elif cmd == '.goto':
            goto_stack.append(len(ans))
            ans.append(None)
        elif cmd == '.cgoto':
            cgoto_stack.append((len(ans), args[0] if args else 'pjif'))
            ans.append(None)
        elif cmd == '.cflabel':
            ans.append(('goto', comefrom_stack.pop()))
        elif cmd == '.label':
            ans[goto_stack.pop()] = ('goto', len(ans))
        elif cmd == '.clabel':
            a, b = cgoto_stack.pop()
            ans[a] = (b, len(ans))
        elif cmd == '.enter':
            varnames_stack.append((dict(varnames_stack[-1][0]), set()))
        elif cmd == '.declvar' and args[0] not in varnames_stack[-1][1]:
            ans.append(('pushc', None))
            varnames_stack[-1][1].add(args[0])
            varnames_stack[-1][0][args[0]] = varnames_stack[-1][0][0]
            varnames_stack[-1][0][0] += 1
#           print(args[0], 'is at', varnames_stack[-1][0][args[0]])
        elif cmd == '.declvar': pass
        elif cmd == '.popvar':
            if args[0] not in varnames_stack[-1][1]:
                varnames_stack[-1][1].add(args[0])
                varnames_stack[-1][0][args[0]] = varnames_stack[-1][0][0]
                varnames_stack[-1][0][0] += 1
#               print(args[0], 'is at', varnames_stack[-1][0][args[0]])
            else:
                ans.extend((('putfast', varnames_stack[-1][0][args[0]]), ('pop',)))
        elif cmd == '.delvar':
            if args[0].name not in varnames_stack[-1][0]:
                raise lexer.VKSyntaxError.fromLexem(args[0], 'undefined variable `%s\''%args[0].name)
            ans.append(('clrfast', varnames_stack[-1][0][args[0].name]))
        elif cmd == '.setvar':
            if args[0].name not in varnames_stack[-1][0]:
                raise lexer.VKSyntaxError.fromLexem(args[0], 'undefined variable `%s\''%args[0].name)
            ans.append(('putfast', varnames_stack[-1][0][args[0].name]))
        elif cmd == '.getvar':
            if args[0].name not in varnames_stack[-1][0]:
                raise lexer.VKSyntaxError.fromLexem(args[0], 'undefined variable `%s\''%args[0].name)
            ans.append(('loadfast', varnames_stack[-1][0][args[0].name]))
        elif cmd == '.leave':
            if varnames_stack[-1][1]:
                ans.append(('popn', len(varnames_stack[-1][1])))
            varnames_stack.pop()
        else:
            ans.append((cmd,)+tuple(args))
    ans.extend((('pushc', None), ('return',)))
    return ans
