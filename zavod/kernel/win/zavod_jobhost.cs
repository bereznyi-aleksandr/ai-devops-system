// ДОКУМЕНТ: win/zavod_jobhost.cs
// ВЕРСИЯ: v0.1  СТАТУС: CANDIDATE
// ДАТА СОЗДАНИЯ: 2026-10-07 22:20 +03:00  ДАТА ОБНОВЛЕНИЯ: 2026-10-07 22:39 +03:00 (DRAFT → CANDIDATE: тесты jobhost и fencer прошли на Windows)
// ИСПОЛНИТЕЛЬ: Claude (сессия fd43469f-418c-4f8b-b94b-32cc0b8d4acf)
// НАЗНАЧЕНИЕ: единица исполнения Windows для надзирателя src/fencer.mjs (протокол §6.2 п.1–3,
//   открытый пункт раздела 18: Job Object). Хозяин создаёт Job Object без права выхода из него
//   (breakaway запрещён), запускает исполнителя приостановленным, помещает его в Job Object и
//   только потом даёт ему работать — так все потомки, в том числе отделённые (detached), остаются
//   в единице. Команды надзирателя — строки в stdin; ответы — строки JSON в stdout (тот же канал,
//   куда пишет исполнитель; ev начинается с JOB_).
//   STATUS        -> {"ev":"JOB_STATUS","active":N,"pids":[...]}
//   KILL <ms>     -> TerminateJobObject, ожидание active=0 -> {"ev":"JOB_KILLED","active":N,"pids":[...]}
//   QUIT или EOF  -> выход хозяина; Job Object закрывается с флагом KILL_ON_JOB_CLOSE, поэтому
//                    гибель хозяина или надзирателя гасит всю единицу (отказ в безопасную сторону).
//   Выход ведущего процесса -> {"ev":"JOB_LEADER_EXIT","code":C}
// ОГРАНИЧЕНИЯ: Windows 8+ (вложенные Job Object). Сборка: csc.exe из .NET Framework 4
//   (win/build_jobhost.sh). Пароли и секреты не читает; окружение исполнителя — окружение хозяина,
//   которое задаёт надзиратель (белый список PASS_ENV).
// ВЫЗОВ: zavod_jobhost.exe <программа> [аргументы...]

using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

static class JobHost
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct STARTUPINFO
    {
        public int cb; public string lpReserved; public string lpDesktop; public string lpTitle;
        public int dwX; public int dwY; public int dwXSize; public int dwYSize;
        public int dwXCountChars; public int dwYCountChars; public int dwFillAttribute; public int dwFlags;
        public short wShowWindow; public short cbReserved2; public IntPtr lpReserved2;
        public IntPtr hStdInput; public IntPtr hStdOutput; public IntPtr hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct PROCESS_INFORMATION { public IntPtr hProcess; public IntPtr hThread; public int dwProcessId; public int dwThreadId; }

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr CreateJobObject(IntPtr attrs, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetInformationJobObject(IntPtr job, int cls, IntPtr info, int len);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool QueryInformationJobObject(IntPtr job, int cls, IntPtr info, int len, IntPtr ret);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool TerminateJobObject(IntPtr job, uint code);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern bool CreateProcess(string app, StringBuilder cmd, IntPtr pa, IntPtr ta, bool inherit,
        uint flags, IntPtr env, string cwd, ref STARTUPINFO si, out PROCESS_INFORMATION pi);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint ResumeThread(IntPtr thread);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint WaitForSingleObject(IntPtr h, uint ms);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool GetExitCodeProcess(IntPtr h, out uint code);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool TerminateProcess(IntPtr h, uint code);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr GetStdHandle(int n);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetHandleInformation(IntPtr h, uint mask, uint flags);

    const int JobObjectBasicAccountingInformation = 1;
    const int JobObjectBasicProcessIdList = 3;
    const int JobObjectExtendedLimitInformation = 9;
    const int JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;
    const uint CREATE_SUSPENDED = 0x4;
    const uint CREATE_NO_WINDOW = 0x08000000;
    const int STARTF_USESTDHANDLES = 0x100;
    const uint HANDLE_FLAG_INHERIT = 1;

    static readonly object OutLock = new object();
    static IntPtr Job;

    static void Say(string json)
    {
        lock (OutLock) { Console.Out.Write(json + "\n"); Console.Out.Flush(); }
    }

    static void Fail(string code, string detail)
    {
        Say("{\"ev\":\"JOB_ERROR\",\"code\":\"" + code + "\",\"detail\":\"" + detail.Replace("\\", "/").Replace("\"", "'") + "\"}");
        Environment.Exit(2);
    }

    // Правило разбора командной строки Windows (CommandLineToArgvW): кавычки и обратные косые.
    static string Quote(string a)
    {
        if (a.Length > 0 && a.IndexOfAny(new[] { ' ', '\t', '"', '\n' }) < 0) return a;
        var sb = new StringBuilder("\"");
        int bs = 0;
        foreach (char c in a)
        {
            if (c == '\\') { bs++; continue; }
            if (c == '"') { sb.Append('\\', bs * 2 + 1); sb.Append('"'); bs = 0; continue; }
            sb.Append('\\', bs); bs = 0; sb.Append(c);
        }
        sb.Append('\\', bs * 2);
        sb.Append('"');
        return sb.ToString();
    }

    static int Active()
    {
        IntPtr buf = Marshal.AllocHGlobal(64);
        try
        {
            if (!QueryInformationJobObject(Job, JobObjectBasicAccountingInformation, buf, 48, IntPtr.Zero))
                throw new Exception("accounting: win32 " + Marshal.GetLastWin32Error());
            return Marshal.ReadInt32(buf, 40); // ActiveProcesses
        }
        finally { Marshal.FreeHGlobal(buf); }
    }

    static List<long> Pids()
    {
        const int n = 1024;
        int size = 8 + IntPtr.Size * n;
        IntPtr buf = Marshal.AllocHGlobal(size);
        var r = new List<long>();
        try
        {
            if (!QueryInformationJobObject(Job, JobObjectBasicProcessIdList, buf, size, IntPtr.Zero))
                throw new Exception("pidlist: win32 " + Marshal.GetLastWin32Error());
            int count = Marshal.ReadInt32(buf, 4);
            for (int i = 0; i < count; i++) r.Add(Marshal.ReadIntPtr(buf, 8 + i * IntPtr.Size).ToInt64());
        }
        finally { Marshal.FreeHGlobal(buf); }
        return r;
    }

    static string State(string ev)
    {
        int active = Active();
        return "{\"ev\":\"" + ev + "\",\"active\":" + active + ",\"pids\":[" + string.Join(",", Pids()) + "]}";
    }

    static int Main(string[] args)
    {
        if (args.Length < 1) Fail("JOBHOST_USAGE", "zavod_jobhost.exe <program> [args...]");

        Job = CreateJobObject(IntPtr.Zero, null);
        if (Job == IntPtr.Zero) Fail("JOB_CREATE_FAILED", new Win32Exception(Marshal.GetLastWin32Error()).Message);
        // Только KILL_ON_JOB_CLOSE; флагов BREAKAWAY_OK и SILENT_BREAKAWAY_OK нет — выйти из единицы нельзя.
        int infoLen = IntPtr.Size == 8 ? 144 : 112;
        IntPtr info = Marshal.AllocHGlobal(infoLen);
        for (int i = 0; i < infoLen; i++) Marshal.WriteByte(info, i, 0);
        Marshal.WriteInt32(info, 16, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE);
        if (!SetInformationJobObject(Job, JobObjectExtendedLimitInformation, info, infoLen))
            Fail("JOB_LIMIT_FAILED", new Win32Exception(Marshal.GetLastWin32Error()).Message);
        Marshal.FreeHGlobal(info);

        var cmd = new StringBuilder();
        foreach (string a in args) { if (cmd.Length > 0) cmd.Append(' '); cmd.Append(Quote(a)); }

        // stdout/stderr исполнителя — те же каналы, что у хозяина; stdin у исполнителя нет.
        IntPtr hOut = GetStdHandle(-11), hErr = GetStdHandle(-12);
        SetHandleInformation(hOut, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
        SetHandleInformation(hErr, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
        var si = new STARTUPINFO();
        si.cb = Marshal.SizeOf(typeof(STARTUPINFO));
        si.dwFlags = STARTF_USESTDHANDLES;
        si.hStdInput = IntPtr.Zero; si.hStdOutput = hOut; si.hStdError = hErr;
        PROCESS_INFORMATION pi;
        if (!CreateProcess(null, cmd, IntPtr.Zero, IntPtr.Zero, true, CREATE_SUSPENDED | CREATE_NO_WINDOW,
                IntPtr.Zero, null, ref si, out pi))
            Fail("JOB_SPAWN_FAILED", new Win32Exception(Marshal.GetLastWin32Error()).Message);
        if (!AssignProcessToJobObject(Job, pi.hProcess))
        {
            int err = Marshal.GetLastWin32Error();
            TerminateProcess(pi.hProcess, 1); // код исполнителя ещё не выполнялся
            Fail("JOB_ASSIGN_FAILED", new Win32Exception(err).Message);
        }
        ResumeThread(pi.hThread);
        Say("{\"ev\":\"JOB_STARTED\",\"pid\":" + pi.dwProcessId + ",\"host_pid\":" +
            System.Diagnostics.Process.GetCurrentProcess().Id + "}");

        var leader = pi.hProcess;
        new Thread(() =>
        {
            WaitForSingleObject(leader, 0xFFFFFFFF);
            uint code; GetExitCodeProcess(leader, out code);
            Say("{\"ev\":\"JOB_LEADER_EXIT\",\"code\":" + (int)code + "}");
        }) { IsBackground = true }.Start();

        string line;
        while ((line = Console.In.ReadLine()) != null)
        {
            line = line.Trim();
            try
            {
                if (line == "STATUS") Say(State("JOB_STATUS"));
                else if (line.StartsWith("KILL"))
                {
                    int ms = 10000;
                    string[] p = line.Split(' ');
                    if (p.Length > 1) int.TryParse(p[1], out ms);
                    if (!TerminateJobObject(Job, 137)) throw new Win32Exception(Marshal.GetLastWin32Error());
                    var until = DateTime.UtcNow.AddMilliseconds(ms);
                    while (Active() > 0 && DateTime.UtcNow < until) Thread.Sleep(20);
                    Say(State("JOB_KILLED"));
                }
                else if (line == "QUIT") break;
            }
            catch (Exception e)
            {
                Say("{\"ev\":\"JOB_ERROR\",\"code\":\"JOB_COMMAND_FAILED\",\"detail\":\"" + e.Message.Replace("\"", "'") + "\"}");
            }
        }
        return 0; // выход закрывает Job Object: KILL_ON_JOB_CLOSE гасит всё, что осталось
    }
}
