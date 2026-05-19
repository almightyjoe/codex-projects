using ConnectionObserver.Core.Models;
using ConnectionObserver.Core.Services;
using Microsoft.Data.Sqlite;

namespace ConnectionObserver.Infrastructure.Storage;

public sealed class SqliteConnectionObserverStore : IConnectionHistoryStore, IDnsRecordStore, IAlertRuleStore
{
    private readonly string _connectionString;

    public SqliteConnectionObserverStore(string databasePath)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(databasePath) ?? ".");
        _connectionString = new SqliteConnectionStringBuilder
        {
            DataSource = databasePath,
            Mode = SqliteOpenMode.ReadWriteCreate,
            Cache = SqliteCacheMode.Shared
        }.ToString();
    }

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenAsync(cancellationToken);
        foreach (var statement in SchemaStatements)
        {
            await using var command = connection.CreateCommand();
            command.CommandText = statement;
            await command.ExecuteNonQueryAsync(cancellationToken);
        }
    }

    public async Task SaveSnapshotAsync(ConnectionSnapshot snapshot, CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenAsync(cancellationToken);
        await using var transaction = connection.BeginTransaction();

        foreach (var item in snapshot.Connections)
        {
            await using var command = connection.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = """
                insert into connections (
                    protocol, local_address, local_port, remote_address, remote_port, state,
                    process_name, process_id, executable_path, country, first_seen, last_seen, observed_at
                ) values (
                    $protocol, $local_address, $local_port, $remote_address, $remote_port, $state,
                    $process_name, $process_id, $executable_path, $country, $first_seen, $last_seen, $observed_at
                );
                """;
            AddConnectionParameters(command, item);
            command.Parameters.AddWithValue("$observed_at", snapshot.CapturedAt.ToString("O"));
            await command.ExecuteNonQueryAsync(cancellationToken);
        }

        await transaction.CommitAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<NetworkConnection>> GetRecentConnectionsAsync(int limit, CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = """
            select protocol, local_address, local_port, remote_address, remote_port, state,
                   process_name, process_id, executable_path, country, first_seen, last_seen
            from connections
            order by observed_at desc, id desc
            limit $limit;
            """;
        command.Parameters.AddWithValue("$limit", limit);

        var rows = new List<NetworkConnection>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            rows.Add(ReadConnection(reader));
        }

        return rows;
    }

    public async Task PurgeOlderThanAsync(DateTimeOffset cutoff, CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenAsync(cancellationToken);
        await using var connectionCommand = connection.CreateCommand();
        connectionCommand.CommandText = "delete from connections where observed_at < $cutoff;";
        connectionCommand.Parameters.AddWithValue("$cutoff", cutoff.ToString("O"));
        await connectionCommand.ExecuteNonQueryAsync(cancellationToken);

        await using var alertCommand = connection.CreateCommand();
        alertCommand.CommandText = "delete from alerts where created_at < $cutoff;";
        alertCommand.Parameters.AddWithValue("$cutoff", cutoff.ToString("O"));
        await alertCommand.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task UpsertAsync(DnsRecord record, CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = """
            insert into dns_records (domain, ip_address, first_seen, last_seen, note)
            values ($domain, $ip_address, $first_seen, $last_seen, $note)
            on conflict(domain, ip_key) do update set
                last_seen = excluded.last_seen,
                note = coalesce(dns_records.note, excluded.note);
            """;
        command.Parameters.AddWithValue("$domain", record.Domain);
        command.Parameters.AddWithValue("$ip_address", ValueOrDbNull(record.IpAddress));
        command.Parameters.AddWithValue("$first_seen", record.FirstSeen.ToString("O"));
        command.Parameters.AddWithValue("$last_seen", record.LastSeen.ToString("O"));
        command.Parameters.AddWithValue("$note", ValueOrDbNull(record.Note));
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task SetNoteAsync(string domain, string? ipAddress, string note, CancellationToken cancellationToken = default)
    {
        await UpsertAsync(new DnsRecord(domain, ipAddress, DateTimeOffset.Now, DateTimeOffset.Now, note), cancellationToken);
    }

    public async Task<IReadOnlyList<DnsRecord>> SearchAsync(string? searchText, int limit, CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = """
            select domain, ip_address, first_seen, last_seen, note
            from dns_records
            where $search is null
               or domain like $searchLike
               or ip_address like $searchLike
               or note like $searchLike
            order by last_seen desc
            limit $limit;
            """;
        command.Parameters.AddWithValue("$search", string.IsNullOrWhiteSpace(searchText) ? DBNull.Value : searchText);
        command.Parameters.AddWithValue("$searchLike", $"%{searchText}%");
        command.Parameters.AddWithValue("$limit", limit);

        var records = new List<DnsRecord>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            records.Add(new DnsRecord(
                reader.GetString(0),
                ReadNullableString(reader, 1),
                DateTimeOffset.Parse(reader.GetString(2)),
                DateTimeOffset.Parse(reader.GetString(3)),
                ReadNullableString(reader, 4)));
        }

        return records;
    }

    public async Task<IReadOnlyList<AlertRule>> GetRulesAsync(CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = "select id, type, condition, severity, is_enabled from alert_rules order by created_at;";

        var rules = new List<AlertRule>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            rules.Add(new AlertRule(
                Guid.Parse(reader.GetString(0)),
                Enum.Parse<AlertRuleType>(reader.GetString(1)),
                reader.GetString(2),
                Enum.Parse<AlertSeverity>(reader.GetString(3)),
                reader.GetBoolean(4)));
        }

        return rules;
    }

    public async Task SaveRuleAsync(AlertRule rule, CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = """
            insert into alert_rules (id, type, condition, severity, is_enabled, created_at, updated_at)
            values ($id, $type, $condition, $severity, $is_enabled, $now, $now)
            on conflict(id) do update set
                type = excluded.type,
                condition = excluded.condition,
                severity = excluded.severity,
                is_enabled = excluded.is_enabled,
                updated_at = excluded.updated_at;
            """;
        var now = DateTimeOffset.Now.ToString("O");
        command.Parameters.AddWithValue("$id", rule.Id.ToString());
        command.Parameters.AddWithValue("$type", rule.Type.ToString());
        command.Parameters.AddWithValue("$condition", rule.Condition);
        command.Parameters.AddWithValue("$severity", rule.Severity.ToString());
        command.Parameters.AddWithValue("$is_enabled", rule.IsEnabled);
        command.Parameters.AddWithValue("$now", now);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task SaveAlertAsync(AlertEvent alertEvent, CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = """
            insert into alerts (
                id, rule_id, severity, description, protocol, local_address, local_port,
                remote_address, remote_port, process_name, process_id, created_at
            ) values (
                $id, $rule_id, $severity, $description, $protocol, $local_address, $local_port,
                $remote_address, $remote_port, $process_name, $process_id, $created_at
            );
            """;
        command.Parameters.AddWithValue("$id", alertEvent.Id.ToString());
        command.Parameters.AddWithValue("$rule_id", ValueOrDbNull(alertEvent.RuleId?.ToString()));
        command.Parameters.AddWithValue("$severity", alertEvent.Severity.ToString());
        command.Parameters.AddWithValue("$description", alertEvent.Description);
        command.Parameters.AddWithValue("$protocol", alertEvent.Connection.Protocol);
        command.Parameters.AddWithValue("$local_address", alertEvent.Connection.LocalAddress);
        command.Parameters.AddWithValue("$local_port", alertEvent.Connection.LocalPort);
        command.Parameters.AddWithValue("$remote_address", ValueOrDbNull(alertEvent.Connection.RemoteAddress));
        command.Parameters.AddWithValue("$remote_port", ValueOrDbNull(alertEvent.Connection.RemotePort));
        command.Parameters.AddWithValue("$process_name", ValueOrDbNull(alertEvent.Connection.ProcessName));
        command.Parameters.AddWithValue("$process_id", ValueOrDbNull(alertEvent.Connection.ProcessId));
        command.Parameters.AddWithValue("$created_at", alertEvent.CreatedAt.ToString("O"));
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<AlertEvent>> GetRecentAlertsAsync(int limit, CancellationToken cancellationToken = default)
    {
        await using var connection = await OpenAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = """
            select id, rule_id, severity, description, protocol, local_address, local_port,
                   remote_address, remote_port, process_name, process_id, created_at
            from alerts
            order by created_at desc
            limit $limit;
            """;
        command.Parameters.AddWithValue("$limit", limit);

        var alerts = new List<AlertEvent>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            var createdAt = DateTimeOffset.Parse(reader.GetString(11));
            var alertConnection = new NetworkConnection(
                reader.GetString(4),
                reader.GetString(5),
                reader.GetInt32(6),
                ReadNullableString(reader, 7),
                ReadNullableInt32(reader, 8),
                "Alert",
                ReadNullableString(reader, 9),
                ReadNullableInt32(reader, 10),
                null,
                null,
                createdAt,
                createdAt);

            alerts.Add(new AlertEvent(
                Guid.Parse(reader.GetString(0)),
                ReadNullableString(reader, 1) is { } ruleId ? Guid.Parse(ruleId) : null,
                Enum.Parse<AlertSeverity>(reader.GetString(2)),
                reader.GetString(3),
                alertConnection,
                createdAt));
        }

        return alerts;
    }

    private async Task<SqliteConnection> OpenAsync(CancellationToken cancellationToken)
    {
        var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = "pragma journal_mode = wal; pragma foreign_keys = on;";
        await command.ExecuteNonQueryAsync(cancellationToken);
        return connection;
    }

    private static void AddConnectionParameters(SqliteCommand command, NetworkConnection item)
    {
        command.Parameters.AddWithValue("$protocol", item.Protocol);
        command.Parameters.AddWithValue("$local_address", item.LocalAddress);
        command.Parameters.AddWithValue("$local_port", item.LocalPort);
        command.Parameters.AddWithValue("$remote_address", ValueOrDbNull(item.RemoteAddress));
        command.Parameters.AddWithValue("$remote_port", ValueOrDbNull(item.RemotePort));
        command.Parameters.AddWithValue("$state", item.State);
        command.Parameters.AddWithValue("$process_name", ValueOrDbNull(item.ProcessName));
        command.Parameters.AddWithValue("$process_id", ValueOrDbNull(item.ProcessId));
        command.Parameters.AddWithValue("$executable_path", ValueOrDbNull(item.ExecutablePath));
        command.Parameters.AddWithValue("$country", ValueOrDbNull(item.Country));
        command.Parameters.AddWithValue("$first_seen", item.FirstSeen.ToString("O"));
        command.Parameters.AddWithValue("$last_seen", item.LastSeen.ToString("O"));
    }

    private static NetworkConnection ReadConnection(SqliteDataReader reader)
    {
        return new NetworkConnection(
            reader.GetString(0),
            reader.GetString(1),
            reader.GetInt32(2),
            ReadNullableString(reader, 3),
            ReadNullableInt32(reader, 4),
            reader.GetString(5),
            ReadNullableString(reader, 6),
            ReadNullableInt32(reader, 7),
            ReadNullableString(reader, 8),
            ReadNullableString(reader, 9),
            DateTimeOffset.Parse(reader.GetString(10)),
            DateTimeOffset.Parse(reader.GetString(11)));
    }

    private static string? ReadNullableString(SqliteDataReader reader, int index)
    {
        return reader.IsDBNull(index) ? null : reader.GetString(index);
    }

    private static int? ReadNullableInt32(SqliteDataReader reader, int index)
    {
        return reader.IsDBNull(index) ? null : reader.GetInt32(index);
    }

    private static object ValueOrDbNull<T>(T? value)
    {
        return value is null ? DBNull.Value : value;
    }

    private static readonly string[] SchemaStatements =
    {
        """
        create table if not exists connections (
            id integer primary key autoincrement,
            protocol text not null,
            local_address text not null,
            local_port integer not null,
            remote_address text null,
            remote_port integer null,
            state text not null,
            process_name text null,
            process_id integer null,
            executable_path text null,
            country text null,
            first_seen text not null,
            last_seen text not null,
            observed_at text not null,
            created_at text not null default current_timestamp
        );
        """,
        """
        create index if not exists ix_connections_observed_at on connections (observed_at desc);
        """,
        """
        create table if not exists dns_records (
            id integer primary key autoincrement,
            domain text not null,
            ip_address text null,
            ip_key text generated always as (ifnull(ip_address, '')) virtual,
            first_seen text not null,
            last_seen text not null,
            note text null,
            created_at text not null default current_timestamp,
            unique(domain, ip_key)
        );
        """,
        """
        create table if not exists alert_rules (
            id text primary key,
            type text not null,
            condition text not null,
            severity text not null,
            is_enabled integer not null,
            created_at text not null,
            updated_at text not null
        );
        """,
        """
        create table if not exists alerts (
            id text primary key,
            rule_id text null,
            severity text not null,
            description text not null,
            protocol text not null,
            local_address text not null,
            local_port integer not null,
            remote_address text null,
            remote_port integer null,
            process_name text null,
            process_id integer null,
            created_at text not null
        );
        """,
        """
        create index if not exists ix_alerts_created_at on alerts (created_at desc);
        """
    };
}
