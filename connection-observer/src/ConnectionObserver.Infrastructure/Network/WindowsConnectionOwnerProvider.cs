using System.Diagnostics;
using System.Net;
using System.Runtime.InteropServices;

namespace ConnectionObserver.Infrastructure.Network;

internal sealed class WindowsConnectionOwnerProvider
{
    private const int AfInet = 2;
    private const int TcpTableOwnerPidAll = 5;
    private const int UdpTableOwnerPid = 1;

    public IReadOnlyList<ConnectionOwner> GetOwners()
    {
        if (!OperatingSystem.IsWindows())
        {
            return Array.Empty<ConnectionOwner>();
        }

        return GetTcpOwners().Concat(GetUdpOwners()).ToArray();
    }

    public ProcessInfo? TryGetProcessInfo(int processId)
    {
        try
        {
            using var process = Process.GetProcessById(processId);
            return new ProcessInfo(process.ProcessName, TryReadPath(process));
        }
        catch
        {
            return null;
        }
    }

    private static string? TryReadPath(Process process)
    {
        try
        {
            return process.MainModule?.FileName;
        }
        catch
        {
            return null;
        }
    }

    private static IEnumerable<ConnectionOwner> GetTcpOwners()
    {
        var bufferSize = 0;
        _ = GetExtendedTcpTable(IntPtr.Zero, ref bufferSize, true, AfInet, TcpTableOwnerPidAll, 0);
        if (bufferSize <= 0)
        {
            yield break;
        }

        var buffer = Marshal.AllocHGlobal(bufferSize);
        try
        {
            var result = GetExtendedTcpTable(buffer, ref bufferSize, true, AfInet, TcpTableOwnerPidAll, 0);
            if (result != 0)
            {
                yield break;
            }

            var rowCount = Marshal.ReadInt32(buffer);
            var rowPointer = IntPtr.Add(buffer, sizeof(int));

            for (var index = 0; index < rowCount; index++)
            {
                var row = Marshal.PtrToStructure<MibTcpRowOwnerPid>(rowPointer);
                yield return new ConnectionOwner(
                    "TCP",
                    new IPAddress(row.LocalAddress).ToString(),
                    ConvertPort(row.LocalPort),
                    new IPAddress(row.RemoteAddress).ToString(),
                    ConvertPort(row.RemotePort),
                    (int)row.OwningPid);

                rowPointer = IntPtr.Add(rowPointer, Marshal.SizeOf<MibTcpRowOwnerPid>());
            }
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
    }

    private static IEnumerable<ConnectionOwner> GetUdpOwners()
    {
        var bufferSize = 0;
        _ = GetExtendedUdpTable(IntPtr.Zero, ref bufferSize, true, AfInet, UdpTableOwnerPid, 0);
        if (bufferSize <= 0)
        {
            yield break;
        }

        var buffer = Marshal.AllocHGlobal(bufferSize);
        try
        {
            var result = GetExtendedUdpTable(buffer, ref bufferSize, true, AfInet, UdpTableOwnerPid, 0);
            if (result != 0)
            {
                yield break;
            }

            var rowCount = Marshal.ReadInt32(buffer);
            var rowPointer = IntPtr.Add(buffer, sizeof(int));

            for (var index = 0; index < rowCount; index++)
            {
                var row = Marshal.PtrToStructure<MibUdpRowOwnerPid>(rowPointer);
                yield return new ConnectionOwner(
                    "UDP",
                    new IPAddress(row.LocalAddress).ToString(),
                    ConvertPort(row.LocalPort),
                    null,
                    null,
                    (int)row.OwningPid);

                rowPointer = IntPtr.Add(rowPointer, Marshal.SizeOf<MibUdpRowOwnerPid>());
            }
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
    }

    private static int ConvertPort(uint rawPort)
    {
        var bytes = BitConverter.GetBytes(rawPort);
        return (bytes[0] << 8) + bytes[1];
    }

    [DllImport("iphlpapi.dll", SetLastError = true)]
    private static extern uint GetExtendedTcpTable(
        IntPtr tcpTable,
        ref int sizePointer,
        bool order,
        int ipVersion,
        int tableClass,
        uint reserved);

    [DllImport("iphlpapi.dll", SetLastError = true)]
    private static extern uint GetExtendedUdpTable(
        IntPtr udpTable,
        ref int sizePointer,
        bool order,
        int ipVersion,
        int tableClass,
        uint reserved);

    [StructLayout(LayoutKind.Sequential)]
    private readonly struct MibTcpRowOwnerPid
    {
        public readonly uint State;
        public readonly uint LocalAddress;
        public readonly uint LocalPort;
        public readonly uint RemoteAddress;
        public readonly uint RemotePort;
        public readonly uint OwningPid;
    }

    [StructLayout(LayoutKind.Sequential)]
    private readonly struct MibUdpRowOwnerPid
    {
        public readonly uint LocalAddress;
        public readonly uint LocalPort;
        public readonly uint OwningPid;
    }
}
