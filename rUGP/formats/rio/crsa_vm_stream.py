"""Sequential, read-only CRsa v18 parsing for the audited PF/PM builds.

Reads every command, native operation field, inline object, CString, pool and
suffix reference in order. Unknown classes/versions and nonzero unparsed tails
raise; there is no signature resynchronization or string-plausibility filter.
The bundled schema contains executable type metadata, not retail game text.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import struct

from rUGP.tools.catalog.rio_inventory import decode_class_name
from .crsa_vm_pool import VmMessageCommand


class NativeVmSchema:
    """Portable descriptor catalog; never loads or executes game code."""

    def __init__(self, game: str):
        path = Path(__file__).with_name("crsa_vm_schema.json")
        catalog = json.loads(path.read_text(encoding="utf-8"))
        if catalog.get("format_version") != 1 or game not in catalog["games"]:
            raise ValueError(f"unsupported CRsa schema: {game}")
        self.metadata = catalog["games"][game]
        self.by_va = {int(key): value for key, value in self.metadata["descriptors"].items()}
        self.types = {name: self.by_va[va] for name, va in self.metadata["types"].items()}

    def descriptor(self, va: int) -> dict:
        try:
            return self.by_va[va]
        except KeyError as error:
            raise VmStreamError(f"unknown native field descriptor: {va:#x}") from error

    def fields(self, va: int) -> list[dict]:
        row = self.descriptor(va)
        if row.get("flags", 0) & 0x70000000 == 0x30000000:
            if "members" not in row:
                raise VmStreamError(f"unresolved native members: {row['name']}")
            return row["members"]
        return []


class VmStreamError(ValueError):
    """The payload does not match the supported native archive grammar."""

class CrsaVmStream:
    def __init__(self, data, model):
        self.data = data
        self.model = model
        self.pos = 0
        self.cache = [dict(kind='object', name='null'), dict(kind='object',name='root')]
        self.preloaded = False
        self.strings = []
        self.events = []
        self.commands = []
        self.refs = []
        self.context = 'header'

    def fail(self, message):
        raise VmStreamError(f'{self.pos:#x} {self.context}: {message}')

    def take(self, n):
        if n < 0 or self.pos+n > len(self.data): self.fail(f'read beyond payload ({n})')
        p = self.pos
        self.pos += n
        return self.data[p:self.pos]

    def u8(self): return self.take(1)[0]
    def u16(self): return struct.unpack('<H', self.take(2))[0]
    def u32(self): return struct.unpack('<I', self.take(4))[0]
    def short(self):
        n = self.u8()
        return self.u16() if n == 255 else n
    def count(self):
        n = self.u16()
        return self.u32() if n == 65535 else n

    def string(self, role):
        start = self.pos
        def length():
            n = self.u8()
            if n < 255: return n
            n = self.u16()
            if n < 65535: return n
            return self.u32()
        units = length()
        width = 1
        if units == 65534:
            width = 2
            units = length()
        if units > 0x1000000: self.fail('oversized CString')
        offset = self.pos
        raw = self.take(units * width)
        try: text = raw.decode('utf-16le' if width == 2 else 'cp932')
        except UnicodeError as error: self.fail(f'invalid CString: {error}')
        value = dict(offset=offset, start=start, end=self.pos, text=text, width=width,
                     role=role, context=self.context)
        self.strings.append(value)
        return value

    def tag(self, mode='class'):
        start = self.pos
        word = self.u16()
        if word == 65535:
            if mode == 'mfc':
                schema = self.u16()
                name = self.take(self.u16()).decode('ascii')
                kind = 'mfc_class'
            elif mode == 'class':
                schema = self.u16()
                encoded = self.take(self.short())
                try: name = decode_class_name(encoded)
                except Exception as e: self.fail(f'invalid class name: {e}')
                kind = 'class'
            else:
                schema = self.u8()
                encoded = self.take(self.short())
                if not encoded.startswith(b'&-'): self.fail(f'unrecognized native type prefix {encoded!r}')
                name = encoded[2:].decode('ascii')
                kind = 'type'
            item = dict(kind=kind, name=name, schema=schema)
            self.events.append(dict(offset=start, end=self.pos, event='declare', index=len(self.cache), **item))
            self.cache.append(item)
            return item, True
        tag = self.u32() if word == 0x7fff else (word & 0x7fff) | (0x80000000 if word & 0x8000 else 0)
        index = tag & 0x7fffffff
        if index >= len(self.cache): self.fail(f'cache index {index} >= {len(self.cache)} ({word:#x})')
        item = self.cache[index]
        is_class = bool(tag & 0x80000000)
        expected = ({'class':'class', 'type':'type', 'mfc':'mfc_class'}[mode]) if is_class else 'object'
        if item['kind'] != expected: self.fail(f'cache kind {index}: {item} expected {expected}')
        self.events.append(dict(offset=start, end=self.pos, event='cache', index=index, mode=expected))
        return item, is_class

    def objref(self, role='reference'):
        if not self.preloaded:
            self.preloaded = True
            n = self.short()
            if n > 128: self.fail(f'ancestor preload {n}')
            for i in range(n): self.cache.append(dict(kind='object',name=f'ancestor_{i}'))
        start = self.pos
        item, is_class = self.tag()
        if not is_class:
            return dict(item, cached=True, reference_offset=start)
        flags = self.u16()
        result = dict(kind='object', name=item['name'], schema=item['schema'], flags=flags, offset=start)
        if flags & 0x40:
            self.cache.append(result)
            result['inline'] = self.inline(item)
        else:
            if flags & 0x108 == 0x108:
                result['key'], result['size'] = self.u32(), self.u32()
            else:
                result['resource_name'] = self.string(role+'.resource_name')
            result['parent'] = self.objref(role+'.parent')
            mode = flags & 3
            if mode == 0: result['ordinal'] = self.u8()
            elif mode == 1: result['ordinal'] = self.u32()
            else: self.fail(f'unsupported native reference mode {mode}')
            self.cache.append(result)
        result['end'] = self.pos
        self.refs.append(dict(offset=start,end=self.pos,role=role,name=result['name'],flags=flags))
        return result

    def object(self):
        item, is_class = self.tag()
        if not is_class: return item
        result = dict(kind='object',name=item['name'],schema=item['schema'])
        self.cache.append(result)
        result['value'] = self.inline(item)
        return result

    def inline(self, item):
        name, schema = item['name'], item['schema']
        if name == 'CPostureMoment' and schema == 6:
            enabled, version, options = self.u8(), self.u8(), self.u8()
            if version != 11: self.fail(f'PostureMoment embedded version {version}')
            flags = self.u32()
            refs = [self.objref('posture.curve') for _ in range(3)]
            self.take(12+6+12)  # vector3, three u16, three float32
            text = self.string('posture.identifier')
            tail = self.u32()
            return dict(version=version,flags=flags,refs=refs,text=text,tail=tail)
        if name == 'CMoveAcsOngen' and schema == 3:
            self.take(12)
            records = 0
            while True:
                kind = self.u8()
                if kind == 0x70: break
                if kind not in (2,3): self.fail(f'curve point type {kind}')
                options = self.u8()
                self.take(4)
                coordinates = 12 if (options & 1 if kind == 3 else options) else 8
                self.take(coordinates)
                if kind == 3: self.take(self.u16()*coordinates)
                if kind == 2 or options & 2:
                    self.mfc_object()
                records += 1
            self.take(15)  # two int32, float32, byte and u16
            return dict(curve_points=records)
        if name in ('CFadeData','CFadeInvert','CFadeCarten','CFadeXsHRasterHOffset','CFadeXsSqrRaster_HRasterV_VRasterH','CFadeMulHorz','CFadeMozaik','CFadeNormal','CFadeRatio','CFadeShock','CFadeHorzLine','CFadeSdtRatio','CFadeSdtMulQube','CFadeStepRatio','CFadeMergeBlack','CFadeRSideCarten','CFadeStretchAnti','CFadeStretch','CFadeSdtSpriteStretch','CFadeOverStretchAnti','CFadeTelevisionWipe','CFadeXsRasterNoize','CFadeXsCircleRaster','CFadeXsSrcRotate','CFadeQubeStretchAnti') and schema == 12:
            if name == 'CFadeCarten': self.take(6)
            count, mode = self.u16(), self.u16()
            refs = [self.objref('fade.resource') for _ in range(3)]
            self.take(24 + count*4)
            if name.startswith('CFadeXs'):
                self.take(6)
                self.take(18 if name == 'CFadeXsSrcRotate' else 11)
            if name == 'CFadeXsRasterNoize': self.take(6)
            if name == 'CFadeXsCircleRaster': self.take(4)
            if name in ('CFadeStretchAnti','CFadeStretch','CFadeSdtSpriteStretch','CFadeOverStretchAnti','CFadeQubeStretchAnti'): self.take(17)
            if name == 'CFadeOverStretchAnti': self.take(8)
            if name == 'CFadeQubeStretchAnti': self.take(27)
            if name == 'CFadeTelevisionWipe': self.take(1)
            return dict(count=count,mode=mode,refs=refs)
        if name == 'CAcsPos' and schema == 2:
            return dict(position=self.take(32).hex())
        if name == 'CDcAgesModelQsT' and schema == 2:
            version = self.u8()
            if version != 1: self.fail(f'model embedded version {version}')
            flags = self.u32()
            self.take(12)
            buffers = []
            for _ in range(2):
                size = self.u32()
                buffers.append(dict(offset=self.pos,size=size))
                self.take(size)
            parts = self.count()
            for _ in range(parts):
                self.objref('model.part.texture')
                self.take(20)  # VCOLOR, two values, vertex and index offsets
            texture = self.objref('model.texture')
            self.take(8)
            return dict(version=version,flags=flags,buffers=buffers,parts=parts,texture=texture)
        self.fail(f'inline CObject {item}')

    def mfc_object(self):
        item, is_class = self.tag('mfc')
        if not is_class: return item
        result = dict(kind='object',name=item['name'],schema=item['schema'])
        self.cache.append(result)
        if item['name'] == 'CMN_Time_2G' and item['schema'] == 0:
            result['value'] = self.u32()
        else:
            self.fail(f'unhandled MFC object {item}')
        return result

    def variant(self, role, wide=False):
        tag = self.u32()
        if tag == 4 and wide:
            typ = self.type_identifier()
            if not typ.get('scalar'): self.fail(f'wide non-scalar {typ}')
            row = self.model.types.get(typ['name'])
            if not row or not 0 < row['fields'] <= 8: self.fail(f'wide literal size {typ}')
            return dict(type=typ['name'], raw=self.take(row['fields']).hex())
        mode = tag & 3
        if mode == 0: return self.objref(role)
        if mode == 1: return self.string(role)
        if mode == 2: return dict(integer=(tag if tag < 0x80000000 else tag-0x100000000)>>2)
        subtype = self.u32()
        if subtype == 0x137: return dict(mode3=subtype,value=self.u32())
        if subtype == 0x138: return dict(mode3=subtype)
        self.fail(f'variant mode 3 subtype {subtype:#x}')

    def type_identifier(self):
        kind = self.u16()
        if kind in (0x2d6b,0x2f1a):
            schema, length = self.u16(), self.u16()
            name = self.take(length).decode('ascii')
            return dict(name=name,schema=schema,scalar=kind==0x2f1a)
        if kind == 0x369e:
            typ, is_type = self.tag('type')
            if not is_type: self.fail('type identifier points to object')
            return typ
        if kind == 0x1e57:
            typ, is_class = self.tag('class')
            if not is_class: self.fail('type identifier points to object')
            return typ
        self.fail(f'unknown type identifier {kind:#x}')

    def field(self, typ, role):
        row = self.model.descriptor(typ)
        flags = row.get('flags', row.get('schema',0)) & 0x7fffffff
        kind = flags & 0x70000000
        if kind >= 0x60000000: return self.objref(role)
        if kind != 0x10000000: self.fail(f'field kind {flags:#x} {row["name"]}')
        if flags == 0x10000000: return self.string(role)
        if flags in (0x11000000,0x12000000,0x13000000): return self.u8()
        if flags in (0x14000000,0x15000000): return self.u16()
        if flags in (0x16000000,0x17000000,0x18000000): return self.u32()
        if flags == 0x19000000: return self.take(8).hex()
        if flags == 0x1b000000: return self.variant(role, row['name']=='_CVmVar64')
        if flags == 0x1c000000: return self.native_object(role)
        if row['name'] == '_VCOLOR' and flags == 0x1a000000 and row['fields']==4: return self.u32()
        if flags == 0x10500000: return self.object()
        if flags not in (0x10200000,0x10400000,0x1a000000,0x1d000000,0x1e000000) and row['fields'] <= 4096:
            return dict(type=row['name'],raw=self.take(row['fields']).hex())
        self.fail(f'unhandled field {row["name"]} {flags:#x}')

    def native_object(self, role):
        item, new = self.tag('type')
        if not new: return item
        row = self.model.types.get(item['name'])
        if not row: self.fail(f'unknown native type {item["name"]}')
        result = dict(kind='object', name=item['name'], schema=item['schema'], fields=[])
        self.cache.append(result)
        for field in self.model.fields(row['va']):
            field_role = f'{role}.{item["name"]}.{field["name"] or field["offset"]}'
            value = self.field(field['type'], field_role)
            result['fields'].append(dict(**field, value=value))
        return result

    def bindings(self, function):
        _header = self.u16()
        n = self.count()
        if n > 65535: self.fail('oversized binding array')
        result = []
        for i in range(n):
            typ = self.type_identifier()
            word = self.u16()
            if word == 0xffff:
                offset = self.u32()
                descriptor = dict(kind='field',name=typ['name'],offset=offset)
                self.cache.append(descriptor)
            else:
                index = self.u32() & 0x7fffffff if word == 0x7fff else word & 0x7fff
                if index >= len(self.cache) or self.cache[index]['kind'] != 'field':
                    self.fail(f'unknown field cache {index}')
                descriptor = self.cache[index]
            value = self.variant(f'generic.binding.{typ["name"]}.{descriptor["offset"]}')
            result.append(dict(descriptor=descriptor,value=value))
        return result

    def call_argument_bindings(self):
        result = []
        for i in range(self.short()):
            flag = self.u16()
            value = self.string(f'call.binding.{i}') if flag & 0x8000 else self.objref(f'call.binding.{i}')
            result.append((flag, value))
        return result

    def command(self, ordinal):
        start = self.pos
        typ, new = self.tag()
        if not new or not typ['name'].startswith('CVm'): self.fail(f'not a command type {typ}')
        if typ['schema'] != 21: self.fail(f'unsupported command schema {typ}')
        name = typ['name']
        self.context = f'command_{ordinal}:{name}'
        body = self.pos
        target, flags = self.u32(), self.u32()
        fields = {}
        if name == 'CVmCall':
            fields['script'] = self.objref('call.script')
            n = self.u16()
            fields['arguments'] = [self.variant(f'call.argument.{i}', True) for i in range(n)]
            fields['bindings'] = self.call_argument_bindings()
        elif name in ('CVmJump','CVmLabel'):
            fields['target'] = self.objref(name+'.target')
        elif name == 'CVmRet': pass
        elif name == 'CVmMsg3':
            group, index = self.u16(), self.u16()
            first, second = self.u8(), self.u8()
            records = [struct.unpack('<3I', self.take(12)) for _ in range(first)]
            voices = [struct.unpack('<4H2B', self.take(10)) for _ in range(second)]
            fields.update(group=group,index=index,first_records=records,second_records=voices)
        elif name == 'CVmGenericMsg':
            fields['receiver'] = self.variant('generic.receiver')
            fields['operation'] = self.native_object('generic')
            fields['bindings'] = self.bindings(fields['operation'])
        elif name == 'CVmFlagOp':
            fields['a'], fields['b'] = self.variant('flag.a'), self.variant('flag.b')
            fields['jump'] = self.objref('flag.jump')
            fields['operation'], fields['mode'], fields['target'] = self.u16(), self.u8(), self.u32()
        elif name == 'CVmSync':
            fields['object'] = self.objref('sync.object')
            fields['mode'], fields['value'] = self.u8(), self.u32()
        elif name == 'CVmSound':
            fields['object'] = self.objref('sound.object')
            kind, options = self.u8(), self.u8()
            fields['kind'],fields['options'] = kind, options
            fields['parameters'] = (self.u16(), self.u16(), self.u16())
            if kind in (2,4): fields['resource'] = self.objref('sound.resource')
            if options & 4:
                if options & 8: fields['position'] = self.objref('sound.position')
                else: fields['position'] = [self.u16() for _ in range(4 if options & 0x10 else 7)]
        elif name == 'CVmDirectionSync':
            mode = self.u32()
            fields['mode'] = mode
            fields['objects'] = [self.objref('direction.object') for _ in range(self.u16())]
            if mode & 0x8000:
                fields['value'] = self.u32()
                fields['argument'] = self.variant('direction.argument')
        elif name == 'CVmBlt':
            fields['fader'] = self.object()
            fields['flags'], fields['kind'], fields['options'] = self.u16(), self.u8(), self.u8()
            fields['arguments'] = [self.variant(f'blt.argument.{i}') for i in range(4)]
        else: self.fail(f'unimplemented command {name}')
        result = dict(order=ordinal,offset=start,body=body,end=self.pos,name=name,schema=typ['schema'],
                      target=target,flags=flags,fields=fields)
        self.commands.append(result)
        return result

    def parse(self):
        if self.pos:
            self.fail('the stream has already been consumed')
        archive_version, archive_flags = self.u16(), self.u16()
        if (archive_version, archive_flags) != (48, 1):
            self.fail(f'unsupported archive preamble {archive_version}/{archive_flags}')
        sentinel, version, allocation, count = self.u32(), self.u32(), self.u32(), self.u32()
        if sentinel != 0xffff0000 or version != 18: self.fail(f'unsupported header {sentinel:#x}/{version}')
        metadata = self.u32()
        for i in range(count): self.command(i+1)
        self.context = 'pool'
        units = self.u32()
        base = self.pos
        self.take(units*2)
        end = self.pos
        self.context = 'suffix'
        references = [self.objref('suffix.reference') for _ in range(self.u16())]
        padding = len(self.data)-self.pos
        if any(self.data[self.pos:]): self.fail(f'nonzero trailing {padding} bytes')
        self.take(padding)
        resources = [{k: item[k] for k in ('name', 'key', 'size', 'ordinal', 'offset', 'end')}
                     for item in self.cache if item.get('kind') == 'object'
                     and item.get('name') == 'CRsa' and 'key' in item]
        return dict(archive_version=archive_version,archive_flags=archive_flags,version=version,
                    allocation=allocation,command_count=count,metadata=metadata,
                    pool_base=base,pool_end=end,pool_units=units,suffix_refs=len(references),zero_padding=padding,
                    classes=dict(Counter(c['name'] for c in self.commands)),
                    commands=self.commands,strings=self.strings,cache_entries=len(self.cache),
                    resource_references=resources)


def native_message_commands(result: dict) -> tuple[VmMessageCommand, ...]:
    """Adapt proven message boundaries without invoking the heuristic finder."""
    commands = []
    for command in result["commands"]:
        if command["name"] != "CVmMsg3":
            continue
        fields = command["fields"]
        commands.append(VmMessageCommand(
            object_offset=command["offset"], body_offset=command["body"],
            end_offset=command["end"], class_reference=None,
            command_offset=command["target"], flags=command["flags"],
            string_group=fields["group"], string_index=fields["index"],
            first_records=tuple(tuple(record) for record in fields["first_records"]),
            second_records=tuple(tuple(record) for record in fields["second_records"]),
        ))
    return tuple(commands)


def parse_crsa_vm_stream(payload: bytes, game: str) -> dict:
    """Parse the entire payload or raise VmStreamError; never returns partial success."""
    return CrsaVmStream(payload, NativeVmSchema(game)).parse()
