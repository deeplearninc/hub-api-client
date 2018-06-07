from vcr import VCR

vcr = VCR(
    cassette_library_dir='tests/cassettes',
    decode_compressed_response=True,
    match_on=['uri', 'method'],
    record_mode='once',
)
