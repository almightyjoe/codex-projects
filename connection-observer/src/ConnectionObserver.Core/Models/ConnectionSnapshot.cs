namespace ConnectionObserver.Core.Models;

public sealed record ConnectionSnapshot(
    DateTimeOffset CapturedAt,
    IReadOnlyCollection<NetworkConnection> Connections)
{
    public int TcpCount => Connections.Count(connection => connection.Protocol.Equals("TCP", StringComparison.OrdinalIgnoreCase));

    public int UdpCount => Connections.Count(connection => connection.Protocol.Equals("UDP", StringComparison.OrdinalIgnoreCase));
}
