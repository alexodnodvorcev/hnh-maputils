#!/usr/bin/env python3

import json
import struct
import sys
import argparse

T_END = 0
T_INT = 1
T_STR = 2
T_COORD = 3
T_UINT8 = 4
T_UINT16 = 5
T_COLOR = 6
T_FCOLOR = 7
T_INT8 = 8          
T_INT16 = 9         
T_NIL = 12
T_BYTES = 14
T_FLOAT32 = 15
T_FLOAT64 = 16
T_MAP = 32
T_LONG = 33


class Read:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def read(self, n):
        r = self.data[self.pos:self.pos + n]
        self.pos += n
        return r

    def u8(self): return self.read(1)[0]
    def i8(self): v = self.u8(); return v if v < 128 else v - 256
    def u16(self): return struct.unpack('>H', self.read(2))[0]
    def i16(self): return struct.unpack('>h', self.read(2))[0]
    def i32(self): return struct.unpack('>i', self.read(4))[0]
    def i64(self): return struct.unpack('>q', self.read(8))[0]
    def f32(self): return struct.unpack('>f', self.read(4))[0]
    def f64(self): return struct.unpack('>d', self.read(8))[0]

    def str(self):
        end = self.data.find(b'\x00', self.pos)
        r = self.data[self.pos:end].decode('utf-8')
        self.pos = end + 1
        return r

    def eom(self): return self.pos >= len(self.data)

    def tipe_to_object(self, t):
        if t == T_NIL: return None
        if t == T_UINT8: return self.u8()
        if t == T_INT8: return self.i8()
        if t == T_UINT16: return self.u16()
        if t == T_INT16: return self.i16()
        if t == T_INT: return self.i32()
        if t == T_LONG: return self.i64()
        if t == T_STR: return self.str()
        if t == T_COORD: return {"__coord__": [self.i32(), self.i32()]}
        if t == T_COLOR: return {"__color__": [self.u8(), self.u8(), self.u8(), self.u8()]}
        if t == T_FCOLOR: return {"__fcolor__": [self.f32(), self.f32(), self.f32(), self.f32()]}
        if t == T_FLOAT32: return self.f32()
        if t == T_FLOAT64: return self.f64()
        if t == T_BYTES:
            l = self.u8()
            if l & 0x80: l = self.i32()
            return {"__bytes__": list(self.read(l))}
        if t == T_MAP: return self.map()
        raise ValueError(f"Unknown type: {t}")

    def list(self):
        r = []
        while not self.eom():
            t = self.u8()
            if t == T_END: break
            r.append(self.tipe_to_object(t))
        return r

    def map(self):
        items = self.list()
        return {str(items[i]): items[i+1] for i in range(0, len(items)-1, 2)}


class Write:
    def __init__(self):
        self.buf = bytearray()

    def w(self, d): self.buf.extend(d)
    def u8(self, v): self.buf.append(v & 0xFF)
    def u16(self, v): self.w(struct.pack('>H', v))
    def i16(self, v): self.w(struct.pack('>h', v))
    def i32(self, v): self.w(struct.pack('>i', v))
    def i64(self, v): self.w(struct.pack('>q', v))
    def f32(self, v): self.w(struct.pack('>f', v))
    def f64(self, v): self.w(struct.pack('>d', v))
    def str(self, s): self.w(s.encode('utf-8')); self.u8(0)

    def tipe_to_object(self, o):
        if o is None: self.u8(T_NIL)
        elif isinstance(o, bool): self.u8(T_UINT8); self.u8(1 if o else 0)
        elif isinstance(o, int):
            if 0 <= o < 256: self.u8(T_UINT8); self.u8(o)
            elif 0 <= o < 65536: self.u8(T_UINT16); self.u16(o)
            elif -128 <= o < 0: self.u8(T_INT8); self.u8(o)
            elif -32768 <= o < 0: self.u8(T_INT16); self.i16(o)
            elif -2147483648 <= o <= 2147483647: self.u8(T_INT); self.i32(o)
            else: self.u8(T_LONG); self.i64(o)
        elif isinstance(o, float): self.u8(T_FLOAT64); self.f64(o)
        elif isinstance(o, str): self.u8(T_STR); self.str(o)
        elif isinstance(o, dict):
            if "__coord__" in o:
                self.u8(T_COORD); self.i32(o["__coord__"][0]); self.i32(o["__coord__"][1])
            elif "__color__" in o:
                self.u8(T_COLOR)
                for c in o["__color__"]: self.u8(c)
            elif "__fcolor__" in o:
                self.u8(T_FCOLOR)
                for c in o["__fcolor__"]: self.f32(c)
            elif "__bytes__" in o:
                self.u8(T_BYTES); d = bytes(o["__bytes__"])
                if len(d) < 128: self.u8(len(d))
                else: self.u8(0x80); self.i32(len(d))
                self.w(d)
            else: self.u8(T_MAP); self.map(o); self.u8(T_END)
        elif isinstance(o, list): self.u8(T_MAP); self.list(o); self.u8(T_END)
        else: raise ValueError(f"Cannot encode: {type(o)}")

    def list(self, items):
        for i in items: self.tipe_to_object(i)

    def map(self, d):
        for k, v in d.items(): self.tipe_to_object(k); self.tipe_to_object(v)

    def get(self): return bytes(self.buf)


def hmap_to_json(hmap_path, json_path=None):
    with open(hmap_path, 'rb') as f:
        r = Read(f.read())
    result = r.list()
    if len(result) == 1 and isinstance(result[0], dict) and "__coord__" not in result[0]:
        result = result[0]
    if json_path:
        with open(json_path, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    return result


def json_to_hmap(json_path, hmap_path=None):
    with open(json_path, 'r') as f:
        data = json.load(f)
    w = Write()
    if isinstance(data, dict): w.tipe_to_object(data)
    elif isinstance(data, list): w.list(data); w.u8(T_END)
    else: w.tipe_to_object(data)
    result = w.get()
    if hmap_path:
        with open(hmap_path, 'wb') as f:
            f.write(result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('-hmap2json', metavar='INPUT')
    p.add_argument('-json2hmap', metavar='INPUT')
    p.add_argument('-o', '--output')
    args = p.parse_args()

    if args.hmap2json:
        r = hmap_to_json(args.hmap2json, args.output)
        if not args.output: print(json.dumps(r, indent=2, ensure_ascii=False))
    elif args.json2hmap:
        r = json_to_hmap(args.json2hmap, args.output)
        if not args.output: sys.stdout.buffer.write(r)
    else: p.print_help(); sys.exit(1)


if __name__ == '__main__':
    main()