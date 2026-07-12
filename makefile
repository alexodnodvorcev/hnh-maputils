.PHONY: test test-long test-convert clean

PY = python3
SCRIPT = src/maputils.py

example.hmap:
	@$(PY) -c "import struct; f=open('example.hmap','wb'); f.write(bytes([2])+b'test_key\x00'+bytes([2])+b'test_value\x00'+bytes([0])); f.close()"

test-convert: example.hmap
	$(PY) $(SCRIPT) -hmap2json example.hmap
	$(PY) $(SCRIPT) -hmap2json example.hmap -o test.json

test-long: example.hmap
	$(PY) $(SCRIPT) -hmap2json example.hmap -o long_test.json
	$(PY) $(SCRIPT) -json2hmap long_test.json -o long_test.hmap
	@diff example.hmap long_test.hmap > /dev/null && echo "test passed" || (echo "test failed"; exit 1)
	@rm -f long_test.json long_test.hmap

test:
	pytest

clean:
	rm -f test.json example.hmap long_test.json long_test.hmap