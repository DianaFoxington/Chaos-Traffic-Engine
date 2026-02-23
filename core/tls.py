import struct
import logging

logger = logging.getLogger('CTE.TLS')

class TLSParser:
    HANDSHAKE = 0x16
    CLIENT_HELLO = 0x01

    @staticmethod
    def is_tls_handshake(data: bytes) -> bool: 
        if len(data) < 6:
            return False

        return (data[0] == TLSParser.HANDSHAKE and 
                data[1] == 0x03 and 
                data[2] in [0x01, 0x02, 0x03])

    @staticmethod
    def is_client_hello(data: bytes) -> bool:

        if not TLSParser.is_tls_handshake(data):
            return False

        if len(data) < 10:
            return False

        return data[5] == TLSParser.CLIENT_HELLO

    @staticmethod
    def extract_sni(data: bytes) -> str:
        try:
            if not TLSParser.is_client_hello(data):
                return ""

            pos = 5 + 4

            if pos + 2 > len(data):
                return ""
            pos += 2

            if pos + 32 > len(data):
                return ""
            pos += 32

            if pos + 1 > len(data):
                return ""
            session_id_len = data[pos]
            pos += 1 + session_id_len

            if pos + 2 > len(data):
                return ""
            cipher_suites_len = struct.unpack('!H', data[pos:pos+2])[0]
            pos += 2 + cipher_suites_len

            if pos + 1 > len(data):
                return ""
            compression_len = data[pos]
            pos += 1 + compression_len

            if pos + 2 > len(data):
                return ""
            extensions_len = struct.unpack('!H', data[pos:pos+2])[0]
            pos += 2

            end = pos + extensions_len
            while pos + 4 <= end and pos + 4 <= len(data):
                ext_type = struct.unpack('!H', data[pos:pos+2])[0]
                ext_len = struct.unpack('!H', data[pos+2:pos+4])[0]
                pos += 4

                if ext_type == 0x0000:
                    if pos + 2 > len(data):
                        return ""
                    sni_list_len = struct.unpack('!H', data[pos:pos+2])[0]
                    p = pos + 2
                    while p + 3 <= pos + 2 + sni_list_len and p + 3 <= len(data):
                        name_type = data[p]
                        name_len = struct.unpack('!H', data[p+1:p+3])[0]
                        p += 3
                        if name_type == 0x00 and p + name_len <= len(data):
                            sni = data[p:p+name_len].decode('ascii', errors='ignore')
                            return sni.lstrip('\x00')
                        p += name_len
                    return ""

                pos += ext_len

            return ""
        except:
            return ""

class TLSFragmenter:

    def __init__(self, chaos_engine, aggressive=True):

        self.chaos = chaos_engine
        self.aggressive = aggressive

    def fragment(self, data: bytes) -> list:

        if not TLSParser.is_client_hello(data):
            return [(data, 0)]

        total_len = len(data)

        if self.aggressive:
            num_fragments = self.chaos.get_fragment_count(min_frags=3, max_frags=7)
        else:
            num_fragments = self.chaos.get_fragment_count(min_frags=2, max_frags=4)

        positions = self.chaos.get_fragment_positions(total_len, num_fragments)

        if not positions:
            logger.debug(f"Cannot fragment safely (len={total_len}), sending whole")
            return [(data, 0)]

        sni = TLSParser.extract_sni(data)
        if sni:
            logger.info(f"🎯 Fragmenting ClientHello for: {sni}")

        logger.debug(f"Splitting into {num_fragments} fragments at positions: {positions}")

        fragments = []
        last_pos = 0

        for pos in positions:
            chunk = data[last_pos:pos]
            delay = self.chaos.get_jitter_delay(base_ms=0.5, variance=2.5)
            fragments.append((chunk, delay))
            last_pos = pos

        final_chunk = data[last_pos:]
        final_delay = self.chaos.get_jitter_delay(base_ms=0.3, variance=1.5)
        fragments.append((final_chunk, final_delay))

        sizes = [len(f[0]) for f in fragments]
        logger.debug(f"Fragment sizes: {sizes}")

        return fragments

    def randomize_record_size(self, data: bytes) -> list:
        if len(data) < 32:
            return [(data, 0)]

        chaos_val = self.chaos._mix_entropy()
        base_size = int(256 + chaos_val * 7936)

        chunks = []
        pos = 0
        while pos < len(data):
            v = self.chaos._mix_entropy()
            size = max(64, int(base_size * (0.7 + v * 0.6)))
            chunk = data[pos:pos+size]
            delay = self.chaos.get_jitter_delay(base_ms=0.1, variance=0.5)
            chunks.append((chunk, delay))
            pos += size

        logger.debug(f"Record randomization: {len(chunks)} chunks, sizes {[len(c[0]) for c in chunks]}")
        return chunks