#!/usr/bin/env python3
"""Convert a Litematica .litematic into Minecraft structure-block .nbt files.

Why: Litematica places blocks one at a time in no dependency order, so a rail
(or the minecart standing on it) goes down before the block beneath it and
immediately pops off. A structure block writes its whole volume at once with no
neighbour updates, so rails, redstone and attached blocks survive.

Structure blocks are capped at 48x48x48, so anything bigger is split into a
grid of tiles; the printed table gives the offset each tile is placed at.

Tags keep their original NBT types all the way through. That matters: an item
stack's Slot is a byte, and writing it back as an int makes the container read
as empty - which would quietly gut every filter hopper in a sorting system.

The schematic's own DataVersion is preserved so the server runs its DataFixer
over the block states on load, which is what upgrades an older schematic.

Usage:
    python litematic2structure.py <file.litematic> <output-dir> [--prefix NAME]
"""

import argparse
import gzip
import os
import struct
import sys

MASK64 = (1 << 64) - 1
MAX_EDGE = 48

TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG = 1, 2, 3, 4
TAG_FLOAT, TAG_DOUBLE = 5, 6
TAG_BYTE_ARRAY, TAG_STRING, TAG_LIST, TAG_COMPOUND = 7, 8, 9, 10
TAG_INT_ARRAY, TAG_LONG_ARRAY = 11, 12


class Tag:
    """An NBT value that remembers its exact tag type."""
    __slots__ = ('t', 'v')

    def __init__(self, t, v):
        self.t = t
        self.v = v

    def __repr__(self):
        return 'Tag(%d, %r)' % (self.t, self.v)


def TInt(v):
    return Tag(TAG_INT, v)


def TDouble(v):
    return Tag(TAG_DOUBLE, v)


def TString(v):
    return Tag(TAG_STRING, v)


def TList(elem_type, items):
    return Tag(TAG_LIST, (elem_type, items))


def TCompound(d):
    return Tag(TAG_COMPOUND, d)


EMPTY_LIST = Tag(TAG_LIST, (TAG_COMPOUND, []))


# --------------------------------------------------------------- NBT reading
class Reader:
    def __init__(self, data):
        self.d = data
        self.i = 0

    def take(self, n):
        v = self.d[self.i:self.i + n]
        self.i += n
        return v

    def u(self, fmt, n):
        return struct.unpack(fmt, self.take(n))[0]

    def name(self):
        return self.take(self.u('>H', 2)).decode('utf-8', 'replace')


def read_payload(r, t):
    if t == TAG_BYTE:
        return Tag(t, r.u('>b', 1))
    if t == TAG_SHORT:
        return Tag(t, r.u('>h', 2))
    if t == TAG_INT:
        return Tag(t, r.u('>i', 4))
    if t == TAG_LONG:
        return Tag(t, r.u('>q', 8))
    if t == TAG_FLOAT:
        return Tag(t, r.u('>f', 4))
    if t == TAG_DOUBLE:
        return Tag(t, r.u('>d', 8))
    if t == TAG_BYTE_ARRAY:
        return Tag(t, list(r.take(r.u('>i', 4))))
    if t == TAG_STRING:
        return Tag(t, r.name())
    if t == TAG_LIST:
        et = r.u('>b', 1)
        n = r.u('>i', 4)
        return Tag(t, (et, [read_payload(r, et) for _ in range(n)]))
    if t == TAG_COMPOUND:
        out = {}
        while True:
            ct = r.u('>b', 1)
            if ct == 0:
                return Tag(t, out)
            key = r.name()
            out[key] = read_payload(r, ct)
    if t == TAG_INT_ARRAY:
        return Tag(t, [r.u('>i', 4) for _ in range(r.u('>i', 4))])
    if t == TAG_LONG_ARRAY:
        return Tag(t, [r.u('>q', 8) for _ in range(r.u('>i', 4))])
    raise ValueError('unknown tag %d at offset %d' % (t, r.i))


def load_nbt(path):
    raw = open(path, 'rb').read()
    if raw[0] == 0x1F and raw[1] == 0x8B:
        raw = gzip.decompress(raw)
    r = Reader(raw)
    t = r.u('>b', 1)
    r.name()
    return read_payload(r, t)


def plain(tag):
    """Unwrap a Tag tree into plain Python, for our own inspection only."""
    if tag.t == TAG_COMPOUND:
        return {k: plain(v) for k, v in tag.v.items()}
    if tag.t == TAG_LIST:
        return [plain(v) for v in tag.v[1]]
    return tag.v


# --------------------------------------------------------------- NBT writing
def write_payload(out, tag):
    t, v = tag.t, tag.v
    if t == TAG_BYTE:
        out(struct.pack('>b', v))
    elif t == TAG_SHORT:
        out(struct.pack('>h', v))
    elif t == TAG_INT:
        out(struct.pack('>i', v))
    elif t == TAG_LONG:
        out(struct.pack('>q', v))
    elif t == TAG_FLOAT:
        out(struct.pack('>f', v))
    elif t == TAG_DOUBLE:
        out(struct.pack('>d', v))
    elif t == TAG_BYTE_ARRAY:
        out(struct.pack('>i', len(v)))
        out(bytes(b & 0xFF for b in v))
    elif t == TAG_STRING:
        b = v.encode('utf-8')
        out(struct.pack('>H', len(b)))
        out(b)
    elif t == TAG_LIST:
        et, items = v
        # Vanilla writes TAG_End as the element type of an empty list.
        out(struct.pack('>b', et if items else 0))
        out(struct.pack('>i', len(items)))
        for it in items:
            write_payload(out, it)
    elif t == TAG_COMPOUND:
        for key, sub in v.items():
            out(struct.pack('>b', sub.t))
            kb = key.encode('utf-8')
            out(struct.pack('>H', len(kb)))
            out(kb)
            write_payload(out, sub)
        out(b'\x00')
    elif t == TAG_INT_ARRAY:
        out(struct.pack('>i', len(v)))
        for n in v:
            out(struct.pack('>i', n))
    elif t == TAG_LONG_ARRAY:
        out(struct.pack('>i', len(v)))
        for n in v:
            out(struct.pack('>q', n))
    else:
        raise ValueError('writer does not handle tag %d' % t)


def save_nbt(path, root):
    buf = bytearray()
    out = buf.extend
    out(struct.pack('>b', TAG_COMPOUND))
    out(struct.pack('>H', 0))
    write_payload(out, root)
    with gzip.open(path, 'wb') as fh:
        fh.write(bytes(buf))


# --------------------------------------------------------- litematic decoding
def bit_at(longs, index, bits):
    """Litematica packs entries contiguously; one may straddle two longs."""
    maxv = (1 << bits) - 1
    start = index * bits
    lo = start >> 6
    hi = ((index + 1) * bits - 1) >> 6
    off = start & 63
    a = longs[lo] & MASK64
    if lo == hi:
        return (a >> off) & maxv
    return ((a >> off) | ((longs[hi] & MASK64) << (64 - off))) & maxv


def region_origin(pos, size):
    """A negative Size means the region runs back from Position."""
    return [pos[a] if size[a] >= 0 else pos[a] + size[a] + 1
            for a in ('x', 'y', 'z')]


def decode(path):
    doc = load_nbt(path)
    blocks = {}        # (x,y,z) -> palette entry as plain dict
    tiles = {}         # (x,y,z) -> Tag compound of block-entity data
    entities = []      # ((x,y,z) floats, Tag compound)

    for _, region in doc.v['Regions'].v.items():
        reg = region.v
        size = plain(reg['Size'])
        pos = plain(reg['Position'])
        w, h, l = abs(size['x']), abs(size['y']), abs(size['z'])
        ox, oy, oz = region_origin(pos, size)

        palette = [plain(p) for p in reg['BlockStatePalette'].v[1]]
        longs = reg['BlockStates'].v
        bits = max(2, (len(palette) - 1).bit_length())

        for y in range(h):
            for z in range(l):
                base = y * w * l + z * w
                for x in range(w):
                    # Air is kept, not skipped. A structure only writes the
                    # blocks it lists, so dropping air leaves whatever terrain
                    # was already there - which entombs a machine placed into
                    # solid ground and silently breaks it.
                    entry = palette[bit_at(longs, base + x, bits)]
                    blocks[(ox + x, oy + y, oz + z)] = entry

        # TileEntity x/y/z are region-local: the same basis as the block array.
        for te in reg.get('TileEntities', EMPTY_LIST).v[1]:
            body = dict(te.v)
            tx = body.pop('x').v
            ty = body.pop('y').v
            tz = body.pop('z').v
            tiles[(ox + tx, oy + ty, oz + tz)] = Tag(TAG_COMPOUND, body)

        # Entity Pos is relative to Position - the corner the region was saved
        # from, not its minimum corner. With a negative Size those offsets are
        # negative, so this adds to Position and not to the origin above.
        for ent in reg.get('Entities', EMPTY_LIST).v[1]:
            p = ent.v.get('Pos')
            if p is None:
                continue
            px, py, pz = [c.v for c in p.v[1]]
            body = dict(ent.v)
            # Block-attached entities (item frames, paintings, leash knots)
            # carry the block they hang on in TileX/TileY/TileZ. Those cannot
            # be written usefully here: the structure loader rewrites the
            # entity's Pos to world coordinates on placement, and the game then
            # rejects any TileXYZ further than 16 blocks from it - which any
            # value known at conversion time would be. Dropping the fields lets
            # the game derive the attachment from the entity's own position.
            for field in ('TileX', 'TileY', 'TileZ'):
                body.pop(field, None)
            entities.append(((pos['x'] + px, pos['y'] + py, pos['z'] + pz),
                             Tag(TAG_COMPOUND, body)))

    return doc, blocks, tiles, entities


# ------------------------------------------------------------------ structure
def build_structure(tile_blocks, tile_tiles, tile_entities, size,
                    data_version, origin=(0, 0, 0)):
    palette = []
    index = {}
    block_tags = []

    for (x, y, z), entry in sorted(tile_blocks.items()):
        props = entry.get('Properties') or {}
        key = (entry['Name'], tuple(sorted(props.items())))
        if key not in index:
            index[key] = len(palette)
            comp = {'Name': TString(entry['Name'])}
            if props:
                comp['Properties'] = TCompound(
                    {k: TString(v) for k, v in props.items()})
            palette.append(TCompound(comp))

        body = {
            'state': TInt(index[key]),
            'pos': TList(TAG_INT, [TInt(x), TInt(y), TInt(z)]),
        }
        te = tile_tiles.get((x, y, z))
        if te is not None:
            body['nbt'] = te
        block_tags.append(TCompound(body))

    ent_tags = []
    for (ex, ey, ez), ent in tile_entities:
        body = dict(ent.v)
        body['Pos'] = TList(TAG_DOUBLE,
                            [TDouble(ex), TDouble(ey), TDouble(ez)])
        # Tile* arrived absolute from decode(); bring them into this tile.
        for field, off in (('TileX', origin[0]), ('TileY', origin[1]),
                           ('TileZ', origin[2])):
            if field in body:
                body[field] = TInt(body[field].v - off)
        ent_tags.append(TCompound({
            'pos': TList(TAG_DOUBLE, [TDouble(ex), TDouble(ey), TDouble(ez)]),
            'blockPos': TList(TAG_INT, [TInt(int(ex // 1)), TInt(int(ey // 1)),
                                        TInt(int(ez // 1))]),
            'nbt': TCompound(body),
        }))

    return TCompound({
        'size': TList(TAG_INT, [TInt(size[0]), TInt(size[1]), TInt(size[2])]),
        'palette': TList(TAG_COMPOUND, palette),
        'blocks': TList(TAG_COMPOUND, block_tags),
        'entities': TList(TAG_COMPOUND, ent_tags),
        'DataVersion': TInt(data_version),
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source')
    ap.add_argument('outdir')
    ap.add_argument('--prefix', default='structure')
    args = ap.parse_args()

    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    doc, blocks, tiles, entities = decode(args.source)
    data_version = doc.v['MinecraftDataVersion'].v

    # Trim to the solid extent so the schematic's empty margin is not carved
    # out of the world, but keep the air inside that extent.
    solid = {q for q, e in blocks.items() if e['Name'] != 'minecraft:air'}
    xs = [p[0] for p in solid]
    ys = [p[1] for p in solid]
    zs = [p[2] for p in solid]
    minx, miny, minz = min(xs), min(ys), min(zs)
    maxx, maxy, maxz = max(xs), max(ys), max(zs)
    blocks = {q: e for q, e in blocks.items()
              if minx <= q[0] <= maxx and miny <= q[1] <= maxy
              and minz <= q[2] <= maxz}
    spanx, spany, spanz = (maxx - minx + 1, maxy - miny + 1,
                           maxz - minz + 1)

    filled = sum(1 for t in tiles.values() if 'Items' in t.v)
    print('實方塊 %d，空氣 %d（會一併清空），方塊實體 %d，實體 %d'
          % (len(solid), len(blocks) - len(solid), len(tiles), len(entities)))
    print('範圍 %d x %d x %d   DataVersion %d'
          % (spanx, spany, spanz, data_version))

    os.makedirs(args.outdir, exist_ok=True)
    nx = (spanx + MAX_EDGE - 1) // MAX_EDGE
    ny = (spany + MAX_EDGE - 1) // MAX_EDGE
    nz = (spanz + MAX_EDGE - 1) // MAX_EDGE
    print('切成 %d x %d x %d 格' % (nx, ny, nz))
    print()

    rows = []
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                x0, y0, z0 = (minx + ix * MAX_EDGE, miny + iy * MAX_EDGE,
                              minz + iz * MAX_EDGE)

                def inside(x, y, z):
                    return (x0 <= x < x0 + MAX_EDGE
                            and y0 <= y < y0 + MAX_EDGE
                            and z0 <= z < z0 + MAX_EDGE)

                tb = {(x - x0, y - y0, z - z0): e
                      for (x, y, z), e in blocks.items() if inside(x, y, z)}
                if not any(e['Name'] != 'minecraft:air'
                           for e in tb.values()):
                    continue
                tt = {(x - x0, y - y0, z - z0): e
                      for (x, y, z), e in tiles.items() if inside(x, y, z)}
                te = [((ex - x0, ey - y0, ez - z0), ent)
                      for (ex, ey, ez), ent in entities
                      if inside(ex, ey, ez)]

                sx = min(MAX_EDGE, spanx - ix * MAX_EDGE)
                sy = min(MAX_EDGE, spany - iy * MAX_EDGE)
                sz = min(MAX_EDGE, spanz - iz * MAX_EDGE)
                name = '%s_x%d_y%d_z%d' % (args.prefix, ix, iy, iz)
                path = os.path.join(args.outdir, name + '.nbt')
                save_nbt(path, build_structure(tb, tt, te, (sx, sy, sz),
                                               data_version, (x0, y0, z0)))
                rows.append((name, ix * MAX_EDGE, iy * MAX_EDGE, iz * MAX_EDGE,
                             len(tb), len(tt), len(te),
                             os.path.getsize(path)))

    print('%-24s %6s %5s %5s %8s %9s %6s %10s'
          % ('檔名', '相對X', 'Y', 'Z', '方塊', '方塊實體', '實體', '大小'))
    for name, dx, dy, dz, nb, nt, ne, sz in rows:
        print('%-24s %6d %5d %5d %8d %9d %6d %9dB'
              % (name, dx, dy, dz, nb, nt, ne, sz))
    print()
    print('共 %d 個檔案' % len(rows))


if __name__ == '__main__':
    main()
