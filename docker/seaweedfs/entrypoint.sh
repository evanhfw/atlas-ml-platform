#!/bin/sh
set -eu

cat > /tmp/s3.json <<EOF
{
  "identities": [
    {
      "name": "atlas",
      "credentials": [
        {
          "accessKey": "$S3_ACCESS_KEY",
          "secretKey": "$S3_SECRET_KEY"
        }
      ],
      "actions": ["Admin", "Read", "List", "Tagging", "Write"]
    }
  ]
}
EOF

exec weed server -s3 -s3.config=/tmp/s3.json -dir=/data -volume.max=100
