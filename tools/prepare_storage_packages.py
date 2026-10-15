#!/usr/bin/env python3
"""Stage a pinned DiskMan source and board guards in an existing native build."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from fetch_pinned_archives import fetch
from prepare_openwrt import extract

ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / 'openwrt/storage'


def replace(path, before, after):
    text = path.read_text()
    if text.count(before) != 1:
        raise ValueError('DiskMan source anchor differs: ' + path.name)
    path.write_text(text.replace(before, after))


def prepare(source, taskbase):
    lock = json.loads((STORAGE / 'sources.lock.json').read_bytes())
    archive = taskbase / 'downloads' / lock['archive']
    fetch(lock['url'], lock['sha256'], archive)
    destination = source / 'package/ty1208z-storage/luci-app-diskman'
    with tempfile.TemporaryDirectory(prefix='diskman-') as folder:
        unpacked = Path(folder) / 'source'
        extract(archive, unpacked, lock['archive_root'])
        package = unpacked / 'applications/luci-app-diskman'
        for name, expected in lock['original_files'].items():
            if hashlib.sha256((package / name).read_bytes()).hexdigest() != expected:
                raise ValueError('DiskMan original source differs: ' + name)
        shutil.copyfile(STORAGE / 'diskman.Makefile', package / 'Makefile')
        shutil.copyfile(STORAGE / 'ty1208z.lua', package / 'luasrc/model/ty1208z_storage.lua')
        # Keep both the original copyright headers and the full license in the APK.
        license_path = package / 'root/usr/share/licenses/luci-app-diskman/LICENSE'
        license_path.parent.mkdir(parents=True)
        shutil.copyfile(unpacked / 'LICENSE', license_path)
        model = package / 'luasrc/model/diskman.lua'
        replace(model, '      table.insert(target_devnames, dev)',
                '      if require("luci.model.ty1208z_storage").allowed_disk(dev) then\n'
                '        table.insert(target_devnames, dev)\n      end')
        replace(model, 'd.get_disk_info = function(device, wakeup)',
                'd.get_disk_info = function(device, wakeup)\n'
                '  assert(require("luci.model.ty1208z_storage").allowed_disk(device), "Unsupported data disk")')
        replace(model, 'd.format_partition = function(partition, fs)',
                'd.format_partition = function(partition, fs)\n'
                '  local ok, message = require("luci.model.ty1208z_storage").idle(partition)\n'
                '  if not ok then return 409, message end')
        for function, arguments, members in (('create_raid', 'rname, rlevel, rmembers', 'rmembers'),
                                             ('create_btrfs', 'blabel, blevel, bmembers', 'bmembers')):
            replace(model, 'd.' + function + ' = function(' + arguments + ')',
                    'd.' + function + ' = function(' + arguments + ')\n'
                    '  if type(' + members + ') ~= "table" then return "ERR: Invalid members" end\n'
                    '  for _, member in pairs(' + members + ') do\n'
                    '    local name = type(member) == "string" and member:match("^/dev/([%w]+)$")\n'
                    '    local ok, message = require("luci.model.ty1208z_storage").idle(name)\n'
                    '    if not ok then return "ERR: " .. message end\n  end')
        replace(model, '  local res = luci.util.exec(cmd .. " 2>&1")\n'
                '  if res and res:lower():match("error+") then\n    return 500, res',
                '  local res = luci.util.exec(cmd .. " 2>&1; printf \'\\nDISKMAN_STATUS=%d\\n\' $?")\n'
                '  if not res or res:match("\\nDISKMAN_STATUS=(%d+)%s*$") ~= "0" then\n'
                '    return 500, res or "Format command failed"')
        controller = package / 'luasrc/controller/diskman.lua'
        for endpoint in ('format_partition', 'mk_p_table'):
            replace(controller, 'call("' + endpoint + '")', 'post("' + endpoint + '")')
        replace(controller, '  if p_table == "GPT" or p_table == "MBR" then',
                '  local ok, message = require("luci.model.ty1208z_storage").idle(dev)\n'
                '  if not ok then luci.http.status(409, message); luci.http.write_json(message); return end\n'
                '  if p_table == "GPT" or p_table == "MBR" then')
        view = package / 'luasrc/view/diskman/partition_info.htm'
        replace(view, 'XHR.get(\'<%=luci.dispatcher.build_url("admin/system/diskman/mk_p_table")%>\'',
                'XHR.post(\'<%=luci.dispatcher.build_url("admin/system/diskman/mk_p_table")%>\'')
        partition = package / 'luasrc/model/cbi/diskman/partition.lua'
        replace(partition, 'local dev = arg[1]', 'local dev = arg[1]\n'
                'local storage = require "luci.model.ty1208z_storage"\n'
                'if not storage.allowed_disk(dev) then\n'
                '  luci.http.status(403, "Unsupported data disk"); return nil\nend')
        replace(partition, '  btn_action.write = function(self, section, value)',
                '  btn_action.write = function(self, section, value)\n'
                '    local ok, message = storage.idle(dev)\n'
                '    if not ok then m.errmessage = message; return end')
        files = {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in package.rglob('*') if p.is_file()}
        if destination.exists():
            existing = {p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in destination.rglob('*') if p.is_file()}
            # luci.mk creates modern locale aliases in the source directory.
            # Accept only byte-identical aliases of the pinned original catalogs.
            for modern, original in (('zh_Hans', 'zh-cn'), ('zh_Hant', 'zh-tw')):
                alias = 'po/' + modern + '/diskman.po'
                if alias not in files and existing.get(alias) == files.get('po/' + original + '/diskman.po'):
                    existing.pop(alias, None)
            if existing != files:
                changed = sorted(name for name in existing.keys() | files.keys()
                                 if existing.get(name) != files.get(name))
                raise ValueError('Existing DiskMan tree differs; inspect it before restaging: ' + ', '.join(changed))
        else:
            shutil.copytree(package, destination)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--taskbase', type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.source, args.taskbase))
