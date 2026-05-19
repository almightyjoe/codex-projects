using ConnectionObserver.Core.Models;

namespace ConnectionObserver.Tests;

public sealed class ConnectionSnapshotTests
{
    [Fact]
    public void CountsTcpAndUdpConnections()
    {
        var now = DateTimeOffset.UtcNow;
        var snapshot = new ConnectionSnapshot(now, new[]
        {
            new NetworkConnection("TCP", "127.0.0.1", 1000, "127.0.0.1", 1001, "Established", null, null, null, null, now, now),
            new NetworkConnection("UDP", "0.0.0.0", 53, null, null, "Listening", null, null, null, null, now, now)
        });

        Assert.Equal(1, snapshot.TcpCount);
        Assert.Equal(1, snapshot.UdpCount);
    }
}
