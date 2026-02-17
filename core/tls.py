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
            
            
            i = 0
            while i < len(data) - 20:
                if data[i:i+2] == b'\x00\x00':
                    try:
                        ext_len = (data[i+2] << 8) | data[i+3]
                        
                        
                        if i + 9 < len(data):
                            sni_type = data[i + 5]
                            if sni_type == 0x00:  # hostname type
                                sni_len = (data[i+6] << 8) | data[i+7]
                                
                                if sni_len > 0 and sni_len < 256 and i + 8 + sni_len <= len(data):
                                    sni = data[i+8:i+8+sni_len].decode('ascii', errors='ignore')
                                    
                                    if '.' in sni and sni.replace('.', '').replace('-', '').isalnum():
                                        return sni
                    except:
                        pass
                
                i += 1
            
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
