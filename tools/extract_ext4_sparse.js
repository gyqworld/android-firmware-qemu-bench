#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

class Sparse {
  constructor(file) {
    this.fd = fs.openSync(file, 'r');
    const h = Buffer.alloc(28);
    fs.readSync(this.fd, h, 0, h.length, 0);
    if (h.readUInt32LE(0) !== 0xed26ff3a) throw new Error('not an Android sparse image');
    this.blockSize = h.readUInt32LE(12);
    this.totalBlocks = h.readUInt32LE(16);
    this.chunks = [];
    let inOff = h.readUInt16LE(8);
    let outBlock = 0;
    for (let i = 0; i < h.readUInt32LE(20); i++) {
      const c = Buffer.alloc(12);
      fs.readSync(this.fd, c, 0, c.length, inOff);
      const type = c.readUInt16LE(0);
      const blocks = c.readUInt32LE(4);
      const totalSize = c.readUInt32LE(8);
      const dataOff = inOff + 12;
      this.chunks.push({ type, outStart: outBlock, outEnd: outBlock + blocks, dataOff, totalSize });
      outBlock += blocks;
      inOff += totalSize;
    }
  }

  read(offset, length) {
    const out = Buffer.alloc(length);
    let done = 0;
    while (done < length) {
      const abs = offset + done;
      const block = Math.floor(abs / this.blockSize);
      const inBlock = abs % this.blockSize;
      const chunk = this.chunks.find(c => block >= c.outStart && block < c.outEnd);
      const max = Math.min(length - done, this.blockSize - inBlock);
      if (!chunk) {
        done += max;
        continue;
      }
      if (chunk.type === 0xcac1) {
        const rawOff = chunk.dataOff + (block - chunk.outStart) * this.blockSize + inBlock;
        fs.readSync(this.fd, out, done, max, rawOff);
      } else if (chunk.type === 0xcac2) {
        const fill = Buffer.alloc(4);
        fs.readSync(this.fd, fill, 0, 4, chunk.dataOff);
        for (let i = 0; i < max; i++) out[done + i] = fill[(inBlock + i) & 3];
      }
      done += max;
    }
    return out;
  }
}

class Raw {
  constructor(file) {
    this.fd = fs.openSync(file, 'r');
  }

  read(offset, length) {
    const out = Buffer.alloc(length);
    fs.readSync(this.fd, out, 0, length, offset);
    return out;
  }
}

class Ext4 {
  constructor(file) {
    const magic = Buffer.alloc(4);
    const fd = fs.openSync(file, 'r');
    fs.readSync(fd, magic, 0, 4, 0);
    fs.closeSync(fd);
    this.dev = magic.readUInt32LE(0) === 0xed26ff3a ? new Sparse(file) : new Raw(file);
    const sb = this.dev.read(1024, 1024);
    if (sb.readUInt16LE(0x38) !== 0xef53) throw new Error('not ext4');
    this.inodesCount = sb.readUInt32LE(0);
    this.blocksCount = sb.readUInt32LE(4);
    this.firstDataBlock = sb.readUInt32LE(20);
    this.logBlockSize = sb.readUInt32LE(24);
    this.blockSize = 1024 << this.logBlockSize;
    this.blocksPerGroup = sb.readUInt32LE(32);
    this.inodesPerGroup = sb.readUInt32LE(40);
    this.inodeSize = sb.readUInt16LE(88) || 128;
    this.descSize = sb.readUInt16LE(254) || 32;
    this.gdtOffset = (this.firstDataBlock + 1) * this.blockSize;
  }

  block(n) {
    return this.dev.read(n * this.blockSize, this.blockSize);
  }

  inode(n) {
    const idx = n - 1;
    const group = Math.floor(idx / this.inodesPerGroup);
    const local = idx % this.inodesPerGroup;
    const gd = this.dev.read(this.gdtOffset + group * this.descSize, this.descSize);
    const tableLo = gd.readUInt32LE(8);
    const tableHi = this.descSize >= 64 ? gd.readUInt32LE(40) : 0;
    const table = tableLo + tableHi * 0x100000000;
    return this.dev.read(table * this.blockSize + local * this.inodeSize, this.inodeSize);
  }

  extents(inode) {
    const ehMagic = inode.readUInt16LE(40);
    if (ehMagic !== 0xf30a) throw new Error('unsupported non-extent inode');
    const out = [];
    const walk = (buf, off) => {
      const entries = buf.readUInt16LE(off + 2);
      const depth = buf.readUInt16LE(off + 6);
      for (let i = 0; i < entries; i++) {
        const e = off + 12 + i * 12;
        if (depth === 0) {
          const lenRaw = buf.readUInt16LE(e + 4);
          const len = lenRaw & 0x7fff;
          const start = buf.readUInt16LE(e + 6) * 0x100000000 + buf.readUInt32LE(e + 8);
          out.push({ logical: buf.readUInt32LE(e), len, start });
        } else {
          const child = buf.readUInt16LE(e + 8) * 0x100000000 + buf.readUInt32LE(e + 4);
          walk(this.block(child), 0);
        }
      }
    };
    walk(inode, 40);
    return out;
  }

  readInode(n) {
    const ino = this.inode(n);
    const mode = ino.readUInt16LE(0);
    let size = ino.readUInt32LE(4);
    if ((mode & 0xf000) === 0x8000) size += ino.readUInt32LE(108) * 0x100000000;
    const out = Buffer.alloc(size);
    for (const ex of this.extents(ino)) {
      const src = this.dev.read(ex.start * this.blockSize, ex.len * this.blockSize);
      src.copy(out, ex.logical * this.blockSize, 0, Math.min(src.length, out.length - ex.logical * this.blockSize));
    }
    return out;
  }

  listDir(p) {
    const ino = this.resolve(p);
    const data = this.readInode(ino);
    const out = [];
    for (let off = 0; off + 8 <= data.length;) {
      const inode = data.readUInt32LE(off);
      const recLen = data.readUInt16LE(off + 4);
      const nameLen = data[off + 6];
      const type = data[off + 7];
      if (!recLen) break;
      if (inode && nameLen) out.push({ name: data.subarray(off + 8, off + 8 + nameLen).toString(), inode, type });
      off += recLen;
    }
    return out;
  }

  resolve(p) {
    let ino = 2;
    for (const part of p.split('/').filter(Boolean)) {
      const ent = this.listDirByInode(ino).find(e => e.name === part);
      if (!ent) throw new Error(`not found: ${p}`);
      ino = ent.inode;
    }
    return ino;
  }

  listDirByInode(ino) {
    const data = this.readInode(ino);
    const out = [];
    for (let off = 0; off + 8 <= data.length;) {
      const inode = data.readUInt32LE(off);
      const recLen = data.readUInt16LE(off + 4);
      const nameLen = data[off + 6];
      const type = data[off + 7];
      if (!recLen) break;
      if (inode && nameLen) out.push({ name: data.subarray(off + 8, off + 8 + nameLen).toString(), inode, type });
      off += recLen;
    }
    return out;
  }

  readPath(p) {
    return this.readInode(this.resolve(p));
  }

  find(re, start = '/', max = 200000) {
    const results = [];
    const visit = (p, ino, depth) => {
      if (results.length >= max || depth > 20) return;
      let ents;
      try { ents = this.listDirByInode(ino); } catch { return; }
      for (const e of ents) {
        if (e.name === '.' || e.name === '..') continue;
        const child = (p === '/' ? '' : p) + '/' + e.name;
        if (re.test(child)) results.push({ path: child, inode: e.inode, type: e.type });
        if (e.type === 2) visit(child, e.inode, depth + 1);
      }
    };
    visit(start, this.resolve(start), 0);
    return results;
  }

  searchText(re, start = '/', maxFileSize = 2 * 1024 * 1024, maxResults = 1000) {
    const results = [];
    const visit = (p, ino, depth) => {
      if (results.length >= maxResults || depth > 20) return;
      let ents;
      try { ents = this.listDirByInode(ino); } catch { return; }
      for (const e of ents) {
        if (e.name === '.' || e.name === '..') continue;
        const child = (p === '/' ? '' : p) + '/' + e.name;
        if (e.type === 2) {
          visit(child, e.inode, depth + 1);
          continue;
        }
        if (e.type !== 1) continue;
        let data;
        try {
          const inode = this.inode(e.inode);
          const size = inode.readUInt32LE(4) + inode.readUInt32LE(108) * 0x100000000;
          if (size > maxFileSize) continue;
          data = this.readInode(e.inode);
        } catch {
          continue;
        }
        if (data.includes(0)) continue;
        const text = data.toString('utf8');
        const match = text.match(re);
        if (!match) continue;
        const line = text.slice(0, match.index).split(/\r?\n/).length;
        const lines = text.split(/\r?\n/);
        results.push({
          path: child,
          line,
          text: lines.slice(Math.max(0, line - 2), Math.min(lines.length, line + 1)).join('\n')
        });
        if (results.length >= maxResults) return;
      }
    };
    visit(start, this.resolve(start), 0);
    return results;
  }
}

function usage() {
  console.error('Usage: node tools/extract_ext4_sparse.js <image> list <dir>');
  console.error('       node tools/extract_ext4_sparse.js <image> find <regex>');
  console.error('       node tools/extract_ext4_sparse.js <image> cat <path>');
  console.error('       node tools/extract_ext4_sparse.js <image> extract <path> <out-file>');
  console.error('       node tools/extract_ext4_sparse.js <image> search <regex> [start-dir]');
  process.exit(2);
}

const [img, cmd, arg, outFile] = process.argv.slice(2);
if (!img || !cmd) usage();
const ext = new Ext4(img);
if (cmd === 'list') console.log(JSON.stringify(ext.listDir(arg || '/'), null, 2));
else if (cmd === 'find') console.log(JSON.stringify(ext.find(new RegExp(arg || '.', 'i')), null, 2));
else if (cmd === 'cat') process.stdout.write(ext.readPath(arg));
else if (cmd === 'extract') {
  if (!arg || !outFile) usage();
  fs.writeFileSync(outFile, ext.readPath(arg));
}
else if (cmd === 'search') console.log(JSON.stringify(ext.searchText(new RegExp(arg || '.', 'i'), outFile || '/'), null, 2));
else usage();
