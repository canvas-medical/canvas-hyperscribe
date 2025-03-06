from datetime import datetime, timezone
from hashlib import sha256
from hmac import new as hmac_new
from http import HTTPStatus
from re import compile as re_compile, DOTALL, search as re_search
from urllib.parse import quote

from requests import get as requests_get, put as requests_put, Response


class AwsS3:
    def __init__(self, aws_key_id: str, aws_secret: str, region: str, bucket: str) -> None:
        self.aws_key_id = aws_key_id
        self.aws_secret = aws_secret
        self.region = region
        self.bucket = bucket

    def is_ready(self) -> bool:
        return bool(self.aws_key_id and self.aws_secret and self.region and self.bucket)

    def headers(self, object_key: str, data: tuple[bytes, str] | None = None) -> dict:
        host = f"{self.bucket}.s3.{self.region}.amazonaws.com"
        # request time
        now = datetime.now(timezone.utc)
        amz_date = now.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = now.strftime('%Y%m%d')

        method = 'PUT'
        if not data:
            method = 'GET'
            data = b'', ''

        binary_data, content_type = data

        payload_hash = sha256(binary_data).hexdigest()  # type: ignore

        # canonical request
        canonical_uri = f"/{quote(object_key)}"  # URL encode the key
        canonical_querystring = ''
        canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
        signed_headers = 'host;x-amz-content-sha256;x-amz-date'
        if content_type:
            canonical_headers = f"content-type:{content_type}\n{canonical_headers}"
            signed_headers = f'content-type;{signed_headers}'

        canonical_request = f"{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

        # string to sign
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{sha256(canonical_request.encode('utf-8')).hexdigest()}"  # type: ignore

        # compute the signature
        k_date = hmac_new(('AWS4' + self.aws_secret).encode('utf-8'), date_stamp.encode('utf-8'), sha256).digest()  # type: ignore
        k_region = hmac_new(k_date, self.region.encode('utf-8'), sha256).digest()  # type: ignore
        k_service = hmac_new(k_region, b's3', sha256).digest()  # type: ignore
        k_signing = hmac_new(k_service, b'aws4_request', sha256).digest()  # type: ignore
        signature = hmac_new(k_signing, string_to_sign.encode('utf-8'), sha256).hexdigest()  # type: ignore

        # build authorization header
        authorization_header = f"{algorithm} Credential={self.aws_key_id}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
        return {
            'Host': host,
            'x-amz-date': amz_date,
            'x-amz-content-sha256': payload_hash,
            'Authorization': authorization_header,
        }

    def access_s3_object(self, object_key: str) -> Response:
        if not self.is_ready():
            return Response()
        headers = self.headers(object_key)
        endpoint = f"https://{headers['Host']}/{object_key}"
        return requests_get(endpoint, headers=headers)

    def upload_text_to_s3(self, object_key: str, data: str) -> Response:
        if not self.is_ready():
            return Response()
        content_type = "text/plain"
        headers = self.headers(object_key, (data.encode(), content_type)) | {
            'Content-Type': content_type,
            'Content-Length': str(len(data)),
        }
        endpoint = f"https://{headers['Host']}/{object_key}"
        return requests_put(endpoint, headers=headers, data=data)

    def list_s3_objects(self) -> list[dict]:
        result: list[dict] = []
        if not self.is_ready():
            return result
        headers = self.headers('')
        endpoint = f"https://{headers['Host']}"
        response = requests_get(endpoint, headers=headers)
        if response.status_code == HTTPStatus.OK.value:
            contents_pattern = re_compile(r'<Contents>(.*?)</Contents>', DOTALL)
            for content_match in contents_pattern.finditer(response.content.decode('utf-8')):
                content_xml = content_match.group(1)
                key_match = re_search(r'<Key>(.*?)</Key>', content_xml)
                size_match = re_search(r'<Size>(.*?)</Size>', content_xml)
                modified_match = re_search(r'<LastModified>(.*?)</LastModified>', content_xml)

                obj_info = {
                    'key': key_match.group(1) if key_match else "",
                    'size': int(size_match.group(1)) if size_match else 0,
                    'lastModified': modified_match.group(1) if modified_match else "",
                }
                result.append(obj_info)

        return result
