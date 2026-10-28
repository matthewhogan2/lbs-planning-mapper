#!/bin/sh
# Downloads the open datasets into backend/data/.
#   - County boundaries: Tailte Éireann, CC BY 4.0
#   - Planning applications: National Planning Application Database
#     (Dept. of Housing), CC BY 4.0 - Mayo only, already in WGS84 (outSR=4326)
set -e
cd "$(dirname "$0")/../backend/data"

echo "Downloading county boundaries..."
curl -G --fail -o counties.geojson \
  "https://services-eu1.arcgis.com/FH5XCsx8rYXqnjF5/arcgis/rest/services/Counties_NationalStatutoryBoundaries_Ungeneralised_2024/FeatureServer/1/query" \
  --data-urlencode "where=Shape__Area > 1000000" \
  --data-urlencode "outFields=ENG_NAME_VALUE" --data-urlencode "orderByFields=Shape__Area DESC" \
  --data-urlencode "maxAllowableOffset=0.0005" \
  --data-urlencode "geometryPrecision=5" \
  --data-urlencode "outSR=4326" \
  --data-urlencode "f=geojson"

SINCE="${1:-2024-01-01}"
echo "Downloading Mayo planning applications received since $SINCE..."
curl -G --fail -o mayo_applications.geojson \
  "https://services.arcgis.com/NzlPQPKn5QF9v2US/arcgis/rest/services/IrishPlanningApplications/FeatureServer/0/query" \
  --data-urlencode "where=PlanningAuthority='Mayo County Council' AND ReceivedDate >= DATE '$SINCE'" \
  --data-urlencode "outFields=ApplicationNumber,DevelopmentDescription,DevelopmentAddress,ApplicationStatus,Decision,ReceivedDate,DecisionDate" \
  --data-urlencode "orderByFields=ReceivedDate DESC" \
  --data-urlencode "resultRecordCount=1000" \
  --data-urlencode "outSR=4326" \
  --data-urlencode "f=geojson"

COUNT=$(grep -o '"type":"Feature"' mayo_applications.geojson | wc -l | tr -d ' ')
echo "Got $COUNT applications."
if [ "$COUNT" -lt 100 ]; then
  echo "Fewer than 100 - rerun with an earlier date, e.g.: sh scripts/download_data.sh 2022-01-01"
fi
ls -lh counties.geojson mayo_applications.geojson
