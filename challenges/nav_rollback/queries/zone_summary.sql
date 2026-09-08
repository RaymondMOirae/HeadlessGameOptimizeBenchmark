SELECT
  name,
  COUNT(*) AS calls,
  ROUND(SUM(dur) / 1000000.0, 3) AS total_ms,
  ROUND(AVG(dur) / 1000000.0, 6) AS avg_ms,
  ROUND(MAX(dur) / 1000000.0, 6) AS max_ms
FROM slice
WHERE dur >= 0 AND name != 'RunMetadata'
GROUP BY name
ORDER BY SUM(dur) DESC, name ASC;
