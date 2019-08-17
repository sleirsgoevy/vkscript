import json, collections

class VKRuntimeError(Exception): pass

class _VKBool:
    __slots__ = ()
    def op_is_true(self): return self
    def __bool__(self): return self

def to_signed(x):
    if x >= 0x80000000: x -= 0x100000000
    return x

class VKCell:
    def op_tonumber(self): raise VKRuntimeError('Numeric value is expected')
    def op_tostring(self): return VKString('')
    def op_toobject(self): return VKObject(None)
    def op_torank(self, rank): 
        if rank == 1: return self.op_tonumber()
        elif rank == 3:
            ans = self.op_tonumber()
            if isinstance(ans, VKInt): ans = VKFloat(float(to_signed(ans.n)))
            return ans
        elif rank == 4: return self.op_toobject()
        elif rank == 7: return self.op_tostring()
        else: assert False
    def op_is_true(self): return False
    def op_getitem(self, item):
        return VKNull()
    def op_setattr(self, attr, value):
        raise VKRuntimeError('setting field ['+attr+'] on not array variable')
    def op_delattr(self, attr):
        raise VKRuntimeError('deleting field ['+attr+'] on not array variable')
    def op_getattr(self, attr):
        if hasattr(self, 'attr_'+attr): return getattr(self, 'attr_'+attr)()
        return VKNull()
    def op_attrfilter(self, attr):
        return VKObject(None)
    def op_update(self): pass
    def __repr__(self):
        return type(self).__name__+'(...)'
    RANK = 7

class VKNull(VKCell): pass

class VKBool(VKCell):
    def __init__(self, b):
        self.b = b
    def op_tonumber(self): return VKInt(1 if self.b else 0)
    def op_tostring(self): return VKString('1' if self.b else '')
    def op_is_true(self): return self.b

class VKInt(VKCell):
    def __init__(self, n):
        self.n = n & 0xffffffff
    def op_tonumber(self): return self
    def op_tostring(self): return VKString(repr(to_signed(self.n)))
    def op_is_true(self): return self.n != 0
    RANK = 1

class VKFloat(VKCell):
    def __init__(self, d):
        self.d = d
    def op_tonumber(self): return self
    def op_tostring(self): return VKString(json.dumps(self.d))
    def op_is_true(self): return self.d != 0
    RANK = 3

def to_raw_number(n):
    if isinstance(n, VKInt): return n.n
    elif isinstance(n, VKFloat): return n.d
    else: assert False

class VKString(VKCell):
    def __init__(self, s):
        self.s = s
    def op_tonumber(self):
        s = self.s.replace('Infinity', 'inf').replace('NaN', 'nan')
        try: return VKInt(int(self.s))
        except ValueError:
            try: return VKFloat(float(self.s))
            except ValueError: pass
        raise VKRuntimeError('Numeric value is expected')
    def op_tostring(self): return self
    def op_is_true(self): return self.s != ''
    def attr_length(self): return len(self.s)
    def method_substr(self, *args):
        if len(args) not in (1, 2): raise VKRuntimeError('Bad argument count for method substr')
        a, b = args+(VKInt(0),)
        try: a = a.op_torank(1).n
        except: return VKString('')
        try: b = b.op_torank(1).n
        except: return VKString('')
        if a < 0: a += len(self.s)
        if a < 0: a = 0
        if b < 0:
            b += len(self.s)
            if b < 0: b = 0
        else: b += a
        if b < a: return VKString('')
        return (VKString(self.s[a:b]), self)
    def method_split(self, *args):
        if len(args) != 1: raise VKRuntimeError('Bad argument count for method split')
        sep = args[0].op_tostring()
        if not sep: return VKObject(None)
        return (VKObject(None, VKObject.enumerate(map(VKString, self.s.split(sep)))), self)

class VKObject(VKCell):
    def __init__(self, parent, init=()):
        assert not isinstance(parent, enumerate)
        self.parent = parent
        self.data = collections.OrderedDict(init)
        for k, v in self.data.items(): v.parent = (self.data, k)
    @staticmethod
    def enumerate(x):
        for i, j in enumerate(x): yield (str(i), j)
    def op_tostring(self): return VKString(','.join(i.op_tostring() for i in self.data.items()))
    def op_toobject(self): return self
    def op_getattr(self, item, length=True):
        if item in self.data: return copy(self.data[item])
        if item == 'length': return VKInt(len(self.data))
        return VKNull()
    def op_getitem(self, item):
        return self.op_getattr(item.op_tostring().s, length=False)
    def op_attrfilter(self, attr):
        ans = VKObject(None)
        for k, v in self.data.items():
            if isinstance(v, VKObject) and attr in v.data:
                ans.data[k] = copy(v.data[attr])
            else:
                ans.data[k] = VKNull()
        return ans
    def op_setattr(self, item, value):
        self2 = VKObject(self.parent, self.data.items())
        self2.data[item] = deepcopy(value, (self2.data, item))
        return self2
    def op_delattr(self, item):
        if item not in self.data: return self
        self2 = VKObject(self.parent, self.data.items())
        del self2.data[item]
        return self2
    def op_update(self):
#       print('op_update:', self.data)
        if self.parent != None:
            self.parent[0][self.parent[1]] = self
        for k, v in self.data.items():
            v.parent = (self.data, k)
    def op_is_true(self): return len(self.data) != 0
    def _normalize_array(self): #copy first
        kv = [(str(i), v) for i, (k, v) in enumerate(self.data.items()) if k.isnumeric()]
        kv2 = [(k, v) for k, v in self.data.items() if not k.isnumeric()]
        self.data = collections.OrderedDict(kv+kv2)
        return len(kv)
    def _splice(self, arrlen, pos, del_cnt, ins): #normalize first
        shift_start = pos + del_cnt
        shift = len(ins) - del_cnt
        if shift > 0:
            for i in range(arrlen - 1, shift_start - 1, -1):
                self.data[str(i + shift)] = self.data[str(i)]
                self.data[str(i + shift)].parent = (self.data, str(i + shift))
        elif shift < 0:
            for i in range(shift_start, arrlen):
                self.data[str(i + shift)] = self.data[str(i)]
                self.data[str(i + shift)].parent = (self.data, str(i + shift))
                del self.data[str(i)]
        for i, j in enumerate(ins):
            self.data[str(pos + i)] = deepcopy(j)
            self.data[str(pos + i)].parent = (self.data, str(pos + i))
    def method_slice(self0, *args):
        self = copy(self0)
        l = self._normalize_array()
        if len(args) not in (1, 2): raise VKRuntimeError('Bad argument count for method slice')
        a, b = args + (None,)
        a = to_raw_number(a.op_tonumber())
        if b != None: b = to_raw_number(b.op_tonumber())
        else: b = l
        if a < 0: a += l
        if a < 0: a = 0
        if b != None:
            if b < 0: b += l
            if b < 0: b = 0
        cnt = int((b - a) // 1)
        a = int(a // 1)
        b = a + cnt
        ans = []
        for i in range(a, b):
            ans.append(deepcopy(self.data[str(i)]))
        return (VKObject(None, VKObject.enumerate(ans)), self0)
    def method_push(self, *args):
        if len(args) != 1: raise VKRuntimeError('Bad argument count for method push')
        idx = max(-1, -1, *(int(k) for k in self.data if k.isnumeric())) + 1
        return (VKNull(), self.op_setattr(str(idx), deepcopy(args[0])))
    def method_pop(self, *args):
        if len(args) != 0: raise VKRuntimeError('Bad argument count for method pop')
        try: idx = next(reversed(self.data))
        except StopIteration: return (VKNull(), self)
        ans = self.data[idx]
        ans.parent = None
        ans = (ans, self.op_delattr(idx))
        return ans
    def method_unshift(self, *args):
        if len(args) != 1: raise VKRuntimeError('Bad argument count for method unshift')
        self = copy(self)
        self._normalize_array()
        self._splice(0, 0, args)
        return (VKNull(), self)
    def method_shift(self, *args):
        if len(args) != 0: raise VKRuntimeError('Bad argument count for method shift')
        self = copy(self)
        self._normalize_array()
        if '0' not in self.data: return (VKNull(), self)
        ans = self.data['0']
        ans.parent = None
        self._splice(0, 1, ())
        return ans
    def method_splice(self, *args):
        if len(args) < 2: raise VKRuntimeError('Bad argument count for method splice')
        self = copy(self)
        self._normalize_array()
        start = args[0].op_torank(1).n
        delcnt = args[1].op_torank(1).n
        self._splice(start, delcnt, args[2:])
        return (VKNull(), self)
    RANK = 4

class VKUserdata(VKCell):
    def op_is_true(self): return True

def outer_to_vkcell(it, parent=None):
    if isinstance(it, VKCell): return it
    elif isinstance(it, bool): return VKBool(it)
    elif isinstance(it, int): return VKInt(it)
    elif isinstance(it, float): return VKFloat(it)
    elif isinstance(it, str): return VKString(it)
    elif isinstance(it, list):
        ans = VKObject(parent)
        for i, j in enumerate(it):
            ans.data[str(i)] = outer_to_vkcell(j, (ans.data, str(i)))
    elif isinstance(it, dict):
        ans = VKObject(parent)
        for k, v in it.items():
            k = str(k)
            ans.data[k] = outer_to_vkcell(v, (ans.data, k))
    elif it is None: return VKNull()
    else:
        raise TypeError("can't convert %r to VKCell"%it)
    return ans

def vkcell_to_outer(it):
    if isinstance(it, _VKBool): return bool(it)
    elif isinstance(it, VKBool): return it.b
    elif isinstance(it, VKInt): return to_signed(it.n)
    elif isinstance(it, VKFloat): return it.d
    elif isinstance(it, VKString): return it.s
    elif isinstance(it, VKObject):
        if list(it.data) == list(map(str, range(len(it.data)))):
            return list(map(vkcell_to_outer, it.data.values()))
        else:
            return {k: vkcell_to_outer(v) for k, v in it.data.items()}
    elif isinstance(it, VKNull): return None
    else: assert False, it

#def copy(x):
#    if isinstance(x, VKObject): return VKObject(x.parent, x.data.items())
#    else: return x

def deepcopy(x, parent=123):
    if isinstance(x, VKObject):
        if parent == 123: parent = x.parent
        ans = VKObject(parent)
        for k, v in x.data.items():
            ans.data[k] = deepcopy(v, (ans.data, k))
        return ans
    else: return x
copy = deepcopy

def NoAPI(func, args):
    raise VKRuntimeError('No API!')

def numeric_op(f):
    def wrapper(*args):
        for i in args: i = i.op_tonumber()
        return f(*args)
    return wrapper

def int_op(f):
    def wrapper(*args):
        for i in args: i = i.op_torank(1)
        return f(*args)
    return wrapper

def ranked_op(f):
    def wrapper(*args):
        rank = 0
        for i in args: rank |= i.RANK
        return f(rank, *(i.op_torank(rank) for i in args))
    return wrapper

@ranked_op
def op_add(rank, a, b):
    if rank == 1: return VKInt((a.n + b.n) & 0xffffffff)
    elif rank == 3: return VKFloat(a.d + b.d)
    elif rank == 4:
        ans = VKObject(None)
        for k, v in a.data.items(): ans.data[k] = v
        for k, v in b.data.items(): ans.data[k] = v
        return ans
    elif rank == 7: return VKString(a.s + b.s)
    else: assert False

def simple_math_op(op, opname, signed=False, int_only=False):
    locals = {}
    ts1 = 'to_signed(' if signed else ''
    ts2 = ')' if signed else ''
    exec(('''
@numeric_op
@ranked_op
def op_{opname}(rank, a, b):
    if rank == 1: return VKInt(({a} {op} {b}))
    elif rank == 3: return VKFloat(a.f {op} b.f)
    else: assert False
''' if not int_only else '''
@int_op
def op_{opname}(a, b):
    return VKInt(({a} {op} {b}))
''').format(opname=opname, a=ts1+'a.n'+ts2, op=op, b=ts1+'b.n'+ts2), globals(), locals)
    return locals['op_'+opname]

op_sub = simple_math_op('-', 'sub')
op_mul = simple_math_op('*', 'mul')
op_div = simple_math_op('/', 'div', signed=True)
op_mod = simple_math_op('%', 'mod', signed=True, int_only=True)
op_bitand = simple_math_op('&', 'and', int_only=True)
op_bitor = simple_math_op('|', 'or', int_only=True)
op_bitshl = simple_math_op('<<', 'bitshl', int_only=True)
op_bitshr = simple_math_op('>>', 'bitshr', signed=True, int_only=True)

def compare_op(op, opname):
    locals = {}
    exec('''
def op_{opname}(a, b):
    if isinstance(a, VKObject) or isinstance(b, VKObject):
        raise VKRuntimeError('Comparing values of different or unsupported types')
    if a.RANK < 4 or b.RANK < 4:
        try:
            a = a.op_tonumber()
            b = b.op_tonumber()
        except VKRuntimeError:
            raise VKRuntimeError('Comparing values of different or unsupported types')
        rank = a.RANK | b.RANK
        a = a.op_torank(a.RANK | b.RANK)
        b = b.op_torank(a.RANK | b.RANK)
        if rank == 1:
            return _VKBool(to_signed(a.n) {op} to_signed(b.n))
        elif rank == 3:
            return _VKBool(a.f {op} b.f)
        else: assert False
    else:
        assert isinstance(a, VKString) and isinstance(b, VKString)
        return _VKBool(a.s {op} b.s)
'''.format(opname=opname, op=op), globals(), locals)
    return locals['op_'+opname]

op_eq = compare_op('==', 'eq')
op_ne = compare_op('!=', 'ne')
op_ge = compare_op('>=', 'ge')
op_gt = compare_op('>', 'gt')
op_le = compare_op('<=', 'le')
op_lt = compare_op('<', 'lt')

def op_not(arg):
    return _VKBool(not arg.op_is_true())

@int_op
def op_invert(arg):
    return VKInt(arg.n ^ 0xffffffff)

@numeric_op
def op_negate(arg):
    if isinstance(arg, VKInt): return VKInt(0x100000000 - arg.n)
    elif isinstance(arg, VKFloat): return VKFloat(-arg.f)
    else: assert False

def op_parseInt(arg):
    arg = arg.op_tostring()
    i = len(arg)
    while i > 0:
        try: return VKInt(int(arg.s[:i]))
        except ValueError: i -= 1
    return VKInt(0)

def op_parseFloat(arg):
    arg = arg.op_tostring()
    i = len(arg)
    while i > 0:
        try: return VKFloat(float(arg.s[:i]))
        except ValueError: i -= 1
    return VKFloat(0.0)

binops = {
    '+': op_add,
    '-': op_sub,
    '*': op_mul,
    '/': op_div,
    '%': op_mod,
    '&': op_bitand,
    '|': op_bitor,
    '<<': op_bitshl,
    '>>': op_bitshr,
    '==': op_eq,
    '!=': op_eq,
    '>=': op_ge,
    '>': op_gt,
    '<=': op_le,
    '<': op_lt
}

unaryops = {
    '!': op_not,
    '~': op_invert,
    '-': op_negate,
    'parseInt': op_parseInt,
    'parseFloat': op_parseFloat
}

def lastn(a, b):
    if b:
        ans = a[-b:]
        del a[-b:]
        return ans
    return []

def exec(*pargs, **args):
    code = pargs[0]
    rpc = pargs[1] if len(pargs) > 1 else NoAPI
    stack = []
    stack.append(outer_to_vkcell(args, (stack, 0)))
    ticks = 0
    pc = 0
    while ticks < 10000:
        for i in stack:
            assert not isinstance(i, VKObject) or all(isinstance(j, str) for j in i.data)
        assert len(set(id(x) for x in stack if isinstance(x, VKObject))) == sum(1 for x in stack if isinstance(x, VKObject))
#       print(pc, code[pc])
#       print(stack)
#       print([getattr(i, 'parent', None) for i in stack])
        ticks += 1
        cmd, *args = code[pc]
        if cmd == 'return':
            return vkcell_to_outer(stack[-1])
        elif cmd == 'binop':
            arg2 = stack.pop()
            arg1 = stack.pop()
            stack.append(binops[args[0]](arg1, arg2))
        elif cmd == 'unaryop':
            stack.append(unaryops[args[0]](stack.pop()))
        elif cmd in ('and', 'or'):
            if (cmd == 'or') == stack[-1].op_is_true():
                pc = args[0]
                continue
            stack.pop()
        elif cmd == 'pop':
            stack.pop()
        elif cmd == 'popn':
            lastn(stack, args[0])
        elif cmd == 'pushc':
            stack.append(outer_to_vkcell(args[0]))
        elif cmd == 'makearr':
            values = lastn(stack, args[0])
            stack.append(VKObject(None, VKObject.enumerate(values)))
        elif cmd == 'makeobj':
            values = lastn(stack, len(args[0]))
            stack.append(VKObject(None, zip(args[0], values)))
        elif cmd == 'apicall':
            stack.append(rpc(stack.pop()))
        elif cmd == 'methodcall':
            values = lastn(stack, args[1])
            this = stack.pop()
            if not hasattr(this, 'method_'+args[0]):
                raise VKRuntimeError('Bad method name')
            stack.extend(getattr(this, 'method_'+args[0])(*values))
        elif cmd == 'arrayget':
            index = stack.pop()
            array = stack.pop()
            stack.append(copy(array.op_getitem(index)))
        elif cmd == 'attrget':
            stack.append(copy(stack.pop().op_getattr(args[0])))
        elif cmd == 'attrset':
            value = copy(stack.pop())
            obj = stack.pop()
            stack.append(value)
            stack.append(obj.op_setattr(args[0], value))
            value.parent = (stack[-1].data, args[0])
        elif cmd == 'update':
            stack.pop().op_update()
        elif cmd == 'attrfilter':
            stack.append(stack.pop().op_attrfilter(args[0]))
        elif cmd == 'pjif':
            if stack.pop().op_is_true(): pc = args[0]
        elif cmd == 'goto':
            pc = args[0]
        elif cmd == 'putfast':
            stack[args[0]] = deepcopy(stack[-1], (stack, args[0]))
        elif cmd == 'clrfast':
            stack[args[0]] = VKNull()
        elif cmd == 'loadfast':
            stack.append(deepcopy(stack[args[0]], (stack, args[0])))
        else: assert False
        pc += 1
    raise VKRuntimeError('Too many operations')
#   print('stuck at pc', pc)
