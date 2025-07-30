from datetime import datetime, UTC
from hashlib import sha256
from hmac import new as hmac_new
from http import HTTPStatus
from re import compile as re_compile, DOTALL, search as re_search
from urllib.parse import quote

from requests import get as requests_get, put as requests_put, Response

from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.aws_s3_object import AwsS3Object


class AwsS3:
    ALGORITHM = "AWS4-HMAC-SHA256"
    SAFE_CHARACTERS = "-._~"

    @classmethod
    def querystring(cls, params: dict | None) -> str:
        result = ""
        if isinstance(params, dict):
            result = "&".join(
                [
                    f"{quote(k, safe=cls.SAFE_CHARACTERS)}={quote(str(v), safe=cls.SAFE_CHARACTERS)}"
                    for k, v in sorted(params.items())
                ],
            )
        return result

    def __init__(self, credentials: AwsS3Credentials) -> None:
        self.aws_key = credentials.aws_key
        self.aws_secret = credentials.aws_secret
        self.region = credentials.region
        self.bucket = credentials.bucket

    def is_ready(self) -> bool:
        return bool(self.aws_key and self.aws_secret and self.region and self.bucket)

    def get_host(self) -> str:
        return f"{self.bucket}.s3.{self.region}.amazonaws.com"

    def get_signature_key(self, amz_date: str, canonical_request: str) -> tuple[str, str]:
        date_stamp = amz_date[:8]
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"

        k_date = hmac_new(("AWS4" + self.aws_secret).encode("utf-8"), date_stamp.encode("utf-8"), sha256).digest()
        k_region = hmac_new(k_date, self.region.encode("utf-8"), sha256).digest()
        k_service = hmac_new(k_region, b"s3", sha256).digest()
        k_signing = hmac_new(k_service, b"aws4_request", sha256).digest()
        string_to_sign = (
            f"{self.ALGORITHM}\n{amz_date}\n{credential_scope}\n{sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )
        signature = hmac_new(k_signing, string_to_sign.encode("utf-8"), sha256).hexdigest()

        return credential_scope, signature

    def headers(self, object_key: str, data: tuple[bytes, str] | None = None, params: dict | None = None) -> dict:
        method = "PUT"
        if not data:
            method = "GET"
            data = b"", ""
        binary_data, content_type = data

        host = self.get_host()
        amz_date = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        payload_hash = sha256(binary_data).hexdigest()
        canonical_uri = f"/{quote(object_key)}"
        canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        if content_type:
            canonical_headers = f"content-type:{content_type}\n{canonical_headers}"
            signed_headers = f"content-type;{signed_headers}"

        canonical_querystring = self.querystring(params)
        canonical_request = (
            f"{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        )

        credential_scope, signature = self.get_signature_key(amz_date, canonical_request)
        authorization_header = (
            f"{self.ALGORITHM} Credential={self.aws_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return {
            "Host": host,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Authorization": authorization_header,
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
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
        }
        endpoint = f"https://{headers['Host']}/{object_key}"
        return requests_put(endpoint, headers=headers, data=data)

    def upload_binary_to_s3(self, object_key: str, binary_data: bytes, content_type: str) -> Response:
        if not self.is_ready():
            return Response()
        headers = self.headers(object_key, (binary_data, content_type)) | {
            "Content-Type": content_type,
            "Content-Length": str(len(binary_data)),
        }
        endpoint = f"https://{headers['Host']}/{object_key}"
        return requests_put(endpoint, headers=headers, data=binary_data)

    def list_s3_objects(self, prefix: str) -> list[AwsS3Object]:
        result: list[AwsS3Object] = []
        if not self.is_ready():
            return result

        continuation_token = None
        truncated_pattern = re_compile(r"<IsTruncated>(true|false)</IsTruncated>")
        token_pattern = re_compile(r"<NextContinuationToken>(.*?)</NextContinuationToken>")

        is_truncated = True
        while is_truncated:
            params: dict[str, int | str] = {
                "list-type": 2,
                "prefix": prefix,
            }
            if continuation_token:
                params["continuation-token"] = continuation_token

            headers = self.headers("", params=params)
            endpoint = f"https://{headers['Host']}"
            response = requests_get(endpoint, params=params, headers=headers)
            response_text = response.content.decode("utf-8")

            if response.status_code != HTTPStatus.OK.value:
                raise Exception(f"S3 response status code {response.status_code} with body {response.text}")

            contents_pattern = re_compile(r"<Contents>(.*?)</Contents>", DOTALL)
            for content_match in contents_pattern.finditer(response_text):
                content_xml = content_match.group(1)
                key_match = re_search(r"<Key>(.*?)</Key>", content_xml)
                size_match = re_search(r"<Size>(.*?)</Size>", content_xml)
                modified_match = re_search(r"<LastModified>(.*?)</LastModified>", content_xml)

                if key_match and size_match and modified_match:
                    result.append(
                        AwsS3Object(
                            key=key_match.group(1),
                            size=int(size_match.group(1)),
                            last_modified=datetime.fromisoformat(modified_match.group(1)),
                        )
                    )

            truncated_match = truncated_pattern.search(response_text)
            is_truncated = bool(truncated_match and truncated_match.group(1) == "true")
            if is_truncated:
                token_match = token_pattern.search(response_text)
                if token_match:
                    continuation_token = token_match.group(1)
                else:
                    break

        return result

    def generate_presigned_url(self, object_key: str, expiration: int) -> str:
        if not self.is_ready():
            return ""

        method = "GET"
        host = self.get_host()
        amz_date = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        payload_hash = "UNSIGNED-PAYLOAD"
        canonical_uri = f"/{quote(object_key)}"
        canonical_headers = f"host:{host}\n"
        signed_headers = "host"

        params = {
            "X-Amz-Algorithm": self.ALGORITHM,
            "X-Amz-Credential": f"{self.aws_key}/{amz_date[:8]}/{self.region}/s3/aws4_request",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(expiration),
            "X-Amz-SignedHeaders": signed_headers,
            "X-Amz-Content-Sha256": payload_hash,
        }
        canonical_querystring = self.querystring(params)
        canonical_request = (
            f"{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        )

        _, signature = self.get_signature_key(amz_date, canonical_request)
        params["X-Amz-Signature"] = signature

        querystring = self.querystring(params)
        presigned_url = f"https://{host}/{quote(object_key)}?{querystring}"

        return presigned_url
