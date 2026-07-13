#!/usr/bin/env python3
import json
import struct
import sys
import argparse
import zlib
import traceback

T_END = 0
T_INT = 1
T_STR = 2
T_COORD = 3
T_UINT8 = 4
T_UINT16 = 5
T_COLOR = 6
T_FCOLOR = 7
T_INT8 = 9
T_INT16 = 10
T_NIL = 12
T_BYTES = 14
T_FLOAT32 = 15
T_FLOAT64 = 16
T_MAP = 32
T_LONG = 33

class ZRead:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def read(self, n):
        r = self.data[self.pos:self.pos + n]
        self.pos += n
        return r

    def u8(self):
        b = self.read(1)
        return b[0] if b else 0

    def i8(self):
        v = self.u8()
        return v if v < 128 else v - 256

    def u16(self):
        b = self.read(2)
        if len(b) < 2: return 0
        return struct.unpack('<H', b)[0]

    def i16(self):
        b = self.read(2)
        if len(b) < 2: return 0
        return struct.unpack('<h', b)[0]

    def i32(self):
        b = self.read(4)
        if len(b) < 4: return 0
        return struct.unpack('<i', b)[0]

    def i64(self):
        b = self.read(8)
        if len(b) < 8: return 0
        return struct.unpack('<q', b)[0]

    def u64(self):
        b = self.read(8)
        if len(b) < 8: return 0
        return struct.unpack('<Q', b)[0]

    def f32(self):
        b = self.read(4)
        if len(b) < 4: return 0.0
        return struct.unpack('<f', b)[0]

    def f64(self):
        b = self.read(8)
        if len(b) < 8: return 0.0
        return struct.unpack('<d', b)[0]

    def str(self):
        end = self.data.find(b'\x00', self.pos)
        if end == -1:
            r = self.data[self.pos:].decode('utf-8', errors='ignore')
            self.pos = len(self.data)
            return r
        r = self.data[self.pos:end].decode('utf-8', errors='ignore')
        self.pos = end + 1
        return r

    def eom(self):
        return self.pos >= len(self.data)

    def coord(self):
        return {"coord": [self.i32(), self.i32()]}

    def color(self):
        return {"color": [self.u8(), self.u8(), self.u8(), self.u8()]}

    def fcolor(self):
        return {"fcolor": [self.f32(), self.f32(), self.f32(), self.f32()]}

    def bytes_data(self):
        l = self.u8()
        if l & 0x80:
            l = self.i32()
        return {"bytes": list(self.read(l))}

    def tipe_to_object(self, t):
        if t == T_NIL: return None
        if t == T_UINT8: return self.u8()
        if t == T_INT8: return self.i8()
        if t == T_UINT16: return self.u16()
        if t == T_INT16: return self.i16()
        if t == T_INT: return self.i32()
        if t == T_LONG: return self.i64()
        if t == T_STR: return self.str()
        if t == T_COORD: return self.coord()
        if t == T_COLOR: return self.color()
        if t == T_FCOLOR: return self.fcolor()
        if t == T_FLOAT32: return self.f32()
        if t == T_FLOAT64: return self.f64()
        if t == T_BYTES: return self.bytes_data()
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


class ZWrite:
    def __init__(self):
        self.buf = bytearray()

    def w(self, d):
        self.buf.extend(d)

    def u8(self, v):
        self.buf.append(int(v) & 0xFF)

    def u16(self, v):
        self.w(struct.pack('<H', int(v)))

    def i16(self, v):
        self.w(struct.pack('<h', int(v)))

    def i32(self, v):
        self.w(struct.pack('<i', int(v)))

    def i64(self, v):
        self.w(struct.pack('<q', int(v)))

    def f32(self, v):
        self.w(struct.pack('<f', float(v)))

    def f64(self, v):
        self.w(struct.pack('<d', float(v)))

    def str(self, s):
        self.w(s.encode('utf-8'))
        self.u8(0)

    def tipe_to_object(self, o):
        if o is None:
            self.u8(T_NIL)
        elif isinstance(o, bool):
            self.u8(T_UINT8)
            self.u8(1 if o else 0)
        elif isinstance(o, int):
            if 0 <= o < 256:
                self.u8(T_UINT8); self.u8(o)
            elif 0 <= o < 65536:
                self.u8(T_UINT16); self.u16(o)
            elif -128 <= o < 0:
                self.u8(T_INT8); self.u8(o)
            elif -32768 <= o < 0:
                self.u8(T_INT16); self.i16(o)
            elif -2147483648 <= o <= 2147483647:
                self.u8(T_INT); self.i32(o)
            else:
                self.u8(T_LONG); self.i64(o)
        elif isinstance(o, float):
            self.u8(T_FLOAT64); self.f64(o)
        elif isinstance(o, str):
            self.u8(T_STR); self.str(o)
        elif isinstance(o, dict):
            if "coord" in o:
                self.u8(T_COORD)
                self.i32(o["coord"][0])
                self.i32(o["coord"][1])
            elif "color" in o:
                self.u8(T_COLOR)
                for c in o["color"]: self.u8(c)
            elif "fcolor" in o:
                self.u8(T_FCOLOR)
                for c in o["fcolor"]: self.f32(c)
            elif "bytes" in o:
                self.u8(T_BYTES)
                d = bytes(o["bytes"])
                if len(d) < 128:
                    self.u8(len(d))
                else:
                    self.u8(0x80)
                    self.i32(len(d))
                self.w(d)
            else:
                self.u8(T_MAP)
                self.map(o)
                self.u8(T_END)
        elif isinstance(o, list):
            self.u8(T_MAP)
            self.list(o)
            self.u8(T_END)
        else:
            raise ValueError(f"Cannot encode: {type(o)}")

    def list(self, items):
        for i in items:
            self.tipe_to_object(i)

    def map(self, d):
        for k, v in d.items():
            self.tipe_to_object(k)
            self.tipe_to_object(v)

    def get(self):
        return bytes(self.buf)


def read_c_string(data, pos):
    end = data.find(b'\x00', pos)
    if end == -1:
        return data[pos:].decode('utf-8', errors='ignore'), len(data)
    return data[pos:end].decode('utf-8', errors='ignore'), end + 1


def hmap_to_json(hmap_path, json_path=None):
    try:
        with open(hmap_path, 'rb') as f:
            data = f.read()
            
        if data.startswith(b'Haven Mapfile'):
            zlib_start = 15
            try:
                data = zlib.decompress(data[zlib_start:])
            except zlib.error:
                data = zlib.decompress(data[zlib_start:], -15)
                    
        result = []
        pos = 0
        
        while pos < len(data):
            type_name, pos = read_c_string(data, pos)
            if pos >= len(data):
                break
            if not type_name:
                break
            if pos + 4 > len(data):
                break
            length = struct.unpack('<I', data[pos:pos+4])[0]
            pos += 4
            entry_data = data[pos:pos+length]
            pos += length
            r = ZRead(entry_data)
            entry = {"type": type_name, "data_hex": entry_data.hex()}
            
            if type_name == "grid":
                ver = r.u8()
                entry["version"] = ver
                entry["id"] = r.i64()
                entry["segid"] = r.i64()
                entry["mtime"] = r.i64() if ver >= 2 else 0
                entry["sc"] = r.coord()
                ntiles = r.i32()
                if ver >= 4:
                    ntilesets = r.u16()
                elif ver >= 2:
                    ntilesets = r.u16()
                else:
                    ntilesets = r.u8()
                entry["tilesets"] = []
                for _ in range(ntilesets):
                    ts = {"name": r.str(), "ver": r.u16(), "prio": r.u8()}
                    entry["tilesets"].append(ts)
                if ntilesets <= 256:
                    entry["tiles"] = [r.u8() for _ in range(ntiles)]
                else:
                    entry["tiles"] = [r.u16() for _ in range(ntiles)]
                zfmt = r.u8()
                if zfmt == 0:
                    z = r.f32()
                    entry["zmap"] = [z] * ntiles
                elif zfmt == 1:
                    zmin = r.f32()
                    zq = r.f32()
                    entry["zmap"] = [zmin + r.u8() * zq for _ in range(ntiles)]
                elif zfmt == 2:
                    zmin = r.f32()
                    zq = r.f32()
                    entry["zmap"] = [zmin + r.u16() * zq for _ in range(ntiles)]
                elif zfmt == 3:
                    entry["zmap"] = [r.f32() for _ in range(ntiles)]
                entry["overlays"] = []
                while True:
                    resnm = r.str()
                    if resnm == "":
                        break
                    resver = r.u16()
                    ol = {"name": resnm, "ver": resver, "ol": []}
                    i = 0
                    while i < ntiles:
                        b = r.u8()
                        for o in range(8):
                            if i >= ntiles: break
                            ol["ol"].append((b >> o) & 1 == 1)
                            i += 1
                    entry["overlays"].append(ol)
            elif type_name == "mark":
                ver = r.u8()
                entry["version"] = ver
                entry["seg"] = r.i64()
                entry["tc"] = r.coord()
                entry["nm"] = r.str()
                entry["mtype"] = chr(r.u8())
                if entry["mtype"] == 'p':
                    entry["color"] = r.color()
                    if ver >= 2:
                        entry["onmap"] = r.u8() != 0
                elif entry["mtype"] == 's':
                    entry["oid"] = r.i64()
                    entry["res"] = r.str()
                    entry["resver"] = r.u16()
                    if ver >= 3:
                        dlen = r.u8()
                        entry["data"] = list(r.read(dlen))
                    else:
                        entry["data"] = list(entry_data[r.pos:])
            result.append(entry)
            
        if json_path:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            return None
        return result
    except Exception as e:
        print(f"Error reading .hmap: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


def json_to_hmap(json_path, hmap_path=None):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        zout = bytearray()
        
        for entry in data:
            type_name = entry["type"]
            record_data = bytes.fromhex(entry.get("data_hex", ""))
            
            zout.extend(type_name.encode('utf-8'))
            zout.append(0)
            zout.extend(struct.pack('<I', len(record_data)))
            zout.extend(record_data)
            
        out = bytearray(b'Haven Mapfile 1')
        compressed = zlib.compress(bytes(zout), 9)
        out.extend(compressed)
        
        if hmap_path:
            with open(hmap_path, 'wb') as f:
                f.write(out)
            return None
        return bytes(out)
        
    except Exception as e:
        print(f"Error creating .hmap: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('-hmap2json', metavar='INPUT')
    p.add_argument('-json2hmap', metavar='INPUT')
    p.add_argument('-merge', nargs=2, metavar=('INPUT1', 'INPUT2'))
    p.add_argument('-o', '--output')
    args = p.parse_args()
    
    if args.hmap2json:
        r = hmap_to_json(args.hmap2json, args.output)
        if not args.output:
            print(json.dumps(r, indent=2, ensure_ascii=False))
            
    elif args.json2hmap:
        r = json_to_hmap(args.json2hmap, args.output)
        if not args.output:
            sys.stdout.buffer.write(r)
            
    elif args.merge:
        r = merge_hmaps(args.merge[0], args.merge[1], args.output)
        if not args.output:
            print(json.dumps(r, indent=2, ensure_ascii=False))
            
    else:
        p.print_help()


def merge_hmaps(hmap_path1, hmap_path2, output_path=None, deduplicate=True):
    try:
        data1 = hmap_to_json(hmap_path1)
        if data1 is None:
            return None
            
        data2 = hmap_to_json(hmap_path2)
        if data2 is None:
            return None
        
        if deduplicate:
            seen = set()
            result = []
            
            for entry in list(data1) + list(data2):
                if entry["type"] == "grid":
                    key = ("grid", entry.get("id", ""))
                elif entry["type"] == "mark":
                    tc = entry.get("tc", {})
                    key = ("mark", entry.get("seg", ""), 
                           tc.get("coord", [0, 0])[0], 
                           tc.get("coord", [0, 0])[1])
                else:
                    key = (entry["type"], entry.get("data_hex", ""))
                
                if key not in seen:
                    seen.add(key)
                    result.append(entry)
        else:
            result = list(data1) + list(data2)
        
        stats = {
            "map1_entries": len(data1),
            "map2_entries": len(data2),
            "total_entries": len(result),
            "removed_duplicates": len(list(data1)) + len(list(data2)) - len(result)
        }
        
        if output_path:
            zout = bytearray()
            for entry in result:
                type_name = entry["type"]
                record_data = bytes.fromhex(entry.get("data_hex", ""))
                zout.extend(type_name.encode('utf-8'))
                zout.append(0)
                zout.extend(struct.pack('<I', len(record_data)))
                zout.extend(record_data)
            
            out = bytearray(b'Haven Mapfile 1')
            compressed = zlib.compress(bytes(zout), 9)
            out.extend(compressed)
            
            with open(output_path, 'wb') as f:
                f.write(out)
            return None
        
        return {"stats": stats, "entries": result}
        
    except Exception as e:
        print(f"Error merging hmaps: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()