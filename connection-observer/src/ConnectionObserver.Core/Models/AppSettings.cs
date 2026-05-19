namespace ConnectionObserver.Core.Models;

public sealed record AppSettings(
    int NetworkUpdateIntervalSeconds,
    int DataRetentionDays,
    bool HideUdpListeners,
    bool HideLoopbackConnections)
{
    public static AppSettings Default { get; } = new(
        NetworkUpdateIntervalSeconds: 10,
        DataRetentionDays: 28,
        HideUdpListeners: false,
        HideLoopbackConnections: true);
}
