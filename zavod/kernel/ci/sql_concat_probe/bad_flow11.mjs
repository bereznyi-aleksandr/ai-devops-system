// ДОКУМЕНТ: zavod/kernel/ci/sql_concat_probe/bad_flow11.mjs — проба карты 3.3.10.2 (аудит M3310-R10-01..04): четыре
//   примера аудитора дословно, каждый в своём блоке { } (одинаковые имена функций в одном модуле иначе не разбираются).
// ДАТА: 2026-11-02 07:05 +02:00  ИСПОЛНИТЕЛЬ: Claude (сессия 026813c0-b682-4a65-a177-a655b49ea34c)
import { spawn } from 'node:child_process';
{ function alter(_p,a,line){a.push('sh','-c',line)}; function go(line){const argv=['run','--rm','image']; alter('docker',argv,line); spawn('docker',argv)} }
{ function go(line){const argv=['run','--rm','image', ...['x'].flatMap(()=>[...line.split(' ')])]; spawn('docker',argv)} }
{ function go(line){spawn('docker',['run','--rm','image',process.execPath,'--',...line.split(' ')])} }
{ function go(program,sqlFile){spawn('docker',['run','--rm','image',program,'-f',sqlFile])} }
