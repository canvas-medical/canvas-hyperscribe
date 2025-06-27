import os
import sys
import ffmpeg
import json

from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.libraries.aws_s3 import AwsS3



def list_all_for_prefix(prefix, client_s3):
    patients = {}  # count notes
    notes = {}  # count chunks

    objects = client_s3.list_s3_objects(prefix)
    print(f'There are {len(objects)} S3 objects under the prefix {prefix}/')

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

def prepare_for_retrieval(prefix, client_s3):
    objects = client_s3.list_s3_objects(prefix)
    limited_chart_item = [o for o in objects if o.key.endswith('limited_chart.json')][0]
    webm_objects = sorted(
        [o for o in objects if o.key.endswith('.webm') and '/false_starts/' not in o.key],
        key=lambda o: o.key)
    webm_objects.sort(key=lambda o: o.key)
    tuning_case_dir = os.environ["TUNING_CASE_DIRECTORY"]

    # prepare directories
    first_chunk = webm_objects[0]
    first_chunk_path = os.path.join(tuning_case_dir, first_chunk.key)
    output_dir = os.path.dirname(first_chunk_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"TARGET OUTPUT DIR: {output_dir}")

    # get and save limited chart
    limited_chart_path = os.path.join(tuning_case_dir, limited_chart_item.key)
    chart_item_result = client_s3.access_s3_object(limited_chart_item.key)
    # print(str(limited_chart_path))
    with open(limited_chart_path, 'w') as f:
            cj = json.loads(chart_item_result.text)
            f.write(json.dumps(cj, indent=2))
    
    return webm_objects, output_dir

def collate_audio_for_case(webm_objects, output_dir, client_s3):
    first_chunk = webm_objects.pop(0)
    print(first_chunk.key)
    concat_path = os.path.join(output_dir, 'combined_audio.webm')

    # get and save first chunk
    first_chunk_result = client_s3.access_s3_object(first_chunk.key)
    with open(concat_path, 'wb') as f:
            f.write(first_chunk_result.content)

    # get and append all the other chunks
    for item in webm_objects:
        print(item.key)
        item_result = client_s3.access_s3_object(item.key)
        with open(concat_path, 'ab') as f:
            f.write(item_result.content)

    # finally, convert to mp3
    mp3_filepath = os.path.splitext(concat_path)[0] + '.mp3'
    ffmpeg.input(concat_path).output(
        mp3_filepath, format='mp3',
        audio_bitrate='192k').run(overwrite_output=True)

def get_chunks_for_case(webm_objects, client_s3):
    """
    Get each chunk and transform to mp3.
    The first chunk doesn't need prefix.webm (has headers), but the
    subsequent chunks need prefix.webm first, then the chunk webm, 
    then transformation to mp3.
    OUTPUT: a saved shell file to run for building the case.
    """
    tuning_case_dir = os.environ["TUNING_CASE_DIRECTORY"]

    # get and transform first chunk
    print('First chunk')
    first_chunk = webm_objects.pop(0)
    first_chunk_path = os.path.join(tuning_case_dir, first_chunk.key)
    item_result = client_s3.access_s3_object(first_chunk.key)
    with open(first_chunk_path, 'wb') as f:
            f.write(item_result.content)
    mp3_filepath = os.path.splitext(first_chunk_path)[0] + '.mp3'
    print(first_chunk_path)
    print(mp3_filepath)
    ffmpeg.input(first_chunk_path).output(
        mp3_filepath, format='mp3',
        audio_bitrate='192k').run(overwrite_output=True)

    # get all the other chunks, use prefix, then transform
    with open('prefix.webm', 'rb') as ff:
        prefix_bytes = ff.read()

    print(f'Initial prefix bytes: {len(prefix_bytes)}')

    for item in webm_objects:
        print(item.key)
        item_result = client_s3.access_s3_object(item.key)
        chunk_path = os.path.join(tuning_case_dir, item.key)
        print(f'Iteration prefix bytes: {len(prefix_bytes)}')
        with open(chunk_path, 'wb') as f:
            f.write(prefix_bytes)
            f.write(item_result.content)

        # convert to mp3
        mp3_filepath = os.path.splitext(chunk_path)[0] + '.mp3'
        ffmpeg.input(chunk_path).output(
            mp3_filepath, format='mp3',
            audio_bitrate='192k').run(overwrite_output=True)

if __name__ == '__main__':
    credentials = AwsS3Credentials(
        aws_key=os.environ["SuperAwsKey"],
        aws_secret=os.environ["SuperAwsSecret"],
        region="us-west-2",
        bucket="hyperscribe-tuning-case-data",
    )
    
    client_s3 = AwsS3(credentials)
    retrieval_type = sys.argv[1]
    case_prefix = sys.argv[2]
    webm_objects, output_dir = prepare_for_retrieval(case_prefix, client_s3)
    if retrieval_type == 'collated':
        collate_audio_for_case(webm_objects, output_dir, client_s3)
    elif retrieval_type == 'cyclic':
        get_chunks_for_case(webm_objects, client_s3)
    else:
         print(f'Retrieval type unrecognized {retrieval_type}')
