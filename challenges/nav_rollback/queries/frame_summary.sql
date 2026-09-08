SELECT
  COUNT(*) AS frames,
  ROUND(AVG(dur) / 1000000.0, 6) AS avg_ms,
  ROUND((
    SELECT dur FROM slice
    WHERE name = 'Frame' AND dur >= 0
    ORDER BY dur
    LIMIT 1 OFFSET (
      SELECT CAST((COUNT(*) - 1) * 0.95 AS INTEGER)
      FROM slice WHERE name = 'Frame' AND dur >= 0
    )
  ) / 1000000.0, 6) AS p95_ms,
  ROUND(MAX(dur) / 1000000.0, 6) AS max_ms
FROM slice
WHERE name = 'Frame' AND dur >= 0;
