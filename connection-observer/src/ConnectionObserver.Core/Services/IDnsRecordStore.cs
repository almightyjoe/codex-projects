using ConnectionObserver.Core.Models;

namespace ConnectionObserver.Core.Services;

public interface IDnsRecordStore
{
    Task UpsertAsync(DnsRecord record, CancellationToken cancellationToken = default);

    Task SetNoteAsync(string domain, string? ipAddress, string note, CancellationToken cancellationToken = default);

    Task<IReadOnlyList<DnsRecord>> SearchAsync(string? searchText, int limit, CancellationToken cancellationToken = default);
}
