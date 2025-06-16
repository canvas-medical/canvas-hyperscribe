from os import environ
import sys

from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.libraries.aws_s3 import AwsS3



def list_all_for_prefix(prefix, client_s3):
<<<<<<< HEAD
    patients = {} #count notes
    notes = {} #count chunks
=======
    patients = {}  # count notes
    notes = {}  # count chunks

>>>>>>> 56773b4 (case count script)
    objects = client_s3.list_s3_objects(prefix)
    print(f'There are {len(objects)} S3 objects under the prefix {prefix}')

    for item in objects:
        key_parts = item.key.split('/')
        if len(key_parts) >= 3:
            if not (key_parts[1].startswith('patient_') and key_parts[2].startswith('note_')):
                continue
            if key_parts[2] not in notes:
                notes[key_parts[2]] = 0
            if key_parts[-1].endswith('.webm'):
                notes[key_parts[2]] += 1  # increment chunk count
            if key_parts[1] not in patients:
                patients[key_parts[1]] = set()
            patients[key_parts[1]].add(key_parts[2])

        # item_result = client_s3.access_s3_object(item.key)

    p = 0
    n = 0
    for k, v in patients.items():
        p += 1
        n += len(v)
        print(f"{p:>4}: {k} ({len(v)} note{'' if len(v) == 1 else 's'})")

    c = 0
    for v in notes.values():
        c += v 
    print(f'There are {p} patients, {n} notes, and a total of {c} chunks.\n')


if __name__ == '__main__':
    credentials = AwsS3Credentials(
        aws_key=environ["SuperAwsKey"],
        aws_secret=environ["SuperAwsSecret"],
        region="us-west-2",
        bucket="hyperscribe-tuning-case-data",
    )

    list_all_for_prefix(sys.argv[1], AwsS3(credentials))
