#!/usr/bin/env python3
"""Read source images and extract evidence. Never writes to source images/devices."""
import argparse
import hashlib
import json
import re
import struct
import zlib
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_fdt(blob):
    magic, total, off_struct, off_strings, _, version, _, _, strings_size, struct_size = struct.unpack_from('>10I', blob)
    if magic != 0xD00DFEED or version not in (16, 17) or total > len(blob):
        raise ValueError('Invalid FDT header')
    strings = blob[off_strings:off_strings + strings_size]
    cursor = off_struct
    stack = []
    nodes = []
    while cursor < off_struct + struct_size:
        token = struct.unpack_from('>I', blob, cursor)[0]
        cursor += 4
        if token == 1:
            end = blob.index(b'\0', cursor)
            name = blob[cursor:end].decode('utf-8')
            cursor = (end + 4) & ~3
            node = {'path': '/' + '/'.join([x['name'] for x in stack if x['name']] + ([name] if name else [])), 'name': name, 'properties': {}}
            nodes.append(node)
            stack.append(node)
        elif token == 2:
            stack.pop()
        elif token == 3:
            size, name_offset = struct.unpack_from('>II', blob, cursor)
            cursor += 8
            name = strings[name_offset:strings.index(b'\0', name_offset)].decode('utf-8')
            value = blob[cursor:cursor + size]
            if not stack or len(value) != size:
                raise ValueError('Invalid FDT property')
            stack[-1]['properties'][name] = {'hex': value.hex()}
            if value.endswith(b'\0') and all(byte == 0 or 32 <= byte < 127 for byte in value):
                stack[-1]['properties'][name]['strings'] = value[:-1].decode().split('\0')
            if size % 4 == 0:
                stack[-1]['properties'][name]['cells'] = list(struct.unpack('>' + 'I' * (size // 4), value))
            cursor = (cursor + size + 3) & ~3
        elif token == 4:
            pass
        elif token == 9:
            break
        else:
            raise ValueError(f'Invalid FDT token {token}')
    return {'size': total, 'version': version, 'nodes': nodes}


def inspect_image(path, output):
    data = path.read_bytes()
    result = {'file': str(path), 'bytes': len(data), 'sha256': sha256(path), 'uimages': [], 'device_trees': []}
    for hit in re.finditer(b'\x27\x05\x19\x56', data):
        offset = hit.start()
        if offset + 64 > len(data):
            continue
        _, header_crc, timestamp, size, load, entry, data_crc, os_type, arch, image_type, compression, name = struct.unpack_from('>7I4B32s', data, offset)
        if size > len(data) - offset - 64 or os_type != 5 or arch != 2:
            continue
        header = bytearray(data[offset:offset + 64])
        header[4:8] = b'\0' * 4
        result['uimages'].append({'offset': offset, 'name': name.split(b'\0')[0].decode('ascii', 'replace'), 'payload_bytes': size, 'load_address': hex(load), 'entry_address': hex(entry), 'compression': compression, 'timestamp': timestamp, 'header_crc_valid': zlib.crc32(header) == header_crc, 'payload_crc_valid': zlib.crc32(data[offset + 64:offset + 64 + size]) == data_crc})
    for hit in re.finditer(b'\xd0\x0d\xfe\xed', data):
        offset = hit.start()
        try:
            total = struct.unpack_from('>I', data, offset + 4)[0]
            fdt = parse_fdt(data[offset:offset + total])
        except (ValueError, struct.error, IndexError, UnicodeDecodeError):
            continue
        stem = path.name.replace('.', '-') + f'-offset-{offset}'
        dtb_path = output / (stem + '.dtb')
        dtb_path.write_bytes(data[offset:offset + total])
        fdt['offset'] = offset
        fdt['extracted_file'] = dtb_path.name
        result['device_trees'].append(fdt)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    inputs = [workspace / 'fastboot.bin', workspace / 'TTL-hi3798mv100-32bit/fastboot-hi3798mdmo1g.bin', workspace / 'TTL-hi3798mv100-32bit/hi_kernel-mv100-32.bin', workspace / 'TTL-hi3798mv100-32bit/bootargs9-32.bin']
    inputs += list(workspace.glob('*/01.fastboot.img')) + list(workspace.glob('*/11.kernel.img'))
    report = {'status': 'offline-evidence-only; hardware not tested', 'images': [inspect_image(path, output) for path in inputs if path.is_file()]}
    (output / 'image-evidence.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for item in report['images']:
        print(item['file'], item['bytes'], item['sha256'])
        for header in item['uimages']:
            print(' uImage:', header)
        for fdt in item['device_trees']:
            print(' DTB:', fdt['offset'], fdt['size'], len(fdt['nodes']))


if __name__ == '__main__':
    main()
