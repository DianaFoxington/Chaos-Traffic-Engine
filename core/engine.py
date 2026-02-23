import time
import math
import hashlib
import numpy as np
from collections import deque

class ChaosEngine:  
    def __init__(self, connection_id: bytes = None):
        self.connection_id = connection_id or b''

        self.sigma = 10.0
        self.rho = 28.0
        self.beta = 8.0 / 3.0

        self.r = 3.99

        self._initialize_state()

        self.iteration = 0

        self.history = deque(maxlen=1000)
        self.last_lyapunov = 0.0
        self.last_entropy = 0.0
        self.last_correlation_dim = 0.0

    def _initialize_state(self):

        ns_time = time.time_ns()

        seed_data = str(ns_time).encode() + self.connection_id

        hash_digest = hashlib.sha256(seed_data).digest()

        def extract_float(offset: int) -> float:
            val = int.from_bytes(hash_digest[offset:offset+8], 'big')
            return val / (2**64)

        self.x = extract_float(0) * 20 - 10
        self.y = extract_float(8) * 20 - 10
        self.z = extract_float(16) * 40

        self.logistic_x = extract_float(24)

        self.entropy_pool = [extract_float(i) for i in range(0, 32, 4)]

    def _lorenz_step(self, dt: float = 0.01):

        dx = self.sigma * (self.y - self.x) * dt
        dy = (self.x * (self.rho - self.z) - self.y) * dt
        dz = (self.x * self.y - self.beta * self.z) * dt

        self.x += dx
        self.y += dy
        self.z += dz

    def _logistic_step(self):

        self.logistic_x = self.r * self.logistic_x * (1 - self.logistic_x)

    def _mix_entropy(self) -> float:

        self._lorenz_step()
        self._logistic_step()

        lorenz_contrib = (self.x + 10) / 20
        logistic_contrib = self.logistic_x

        mixed = (lorenz_contrib + logistic_contrib) % 1.0

        self.iteration += 1
        time_factor = (self.iteration * 0.618033988749) % 1.0

        final = (mixed + time_factor) % 1.0

        self.history.append(final)

        return final

    def get_fragment_count(self, min_frags: int = 2, max_frags: int = 8) -> int:

        chaos_val = self._mix_entropy()
        count = min_frags + int(chaos_val * (max_frags - min_frags + 1))
        return min(max_frags, max(min_frags, count))

    def get_fragment_positions(self, total_length: int, num_fragments: int) -> list:

        if num_fragments <= 1:
            return []

        positions = []

        safe_start = 10
        safe_end = total_length - 10
        safe_range = safe_end - safe_start

        if safe_range < num_fragments - 1:
            return []

        for i in range(num_fragments - 1):
            chaos_val = self._mix_entropy()

            segment_size = safe_range / num_fragments
            segment_base = safe_start + (i + 0.3) * segment_size
            segment_variance = segment_size * 0.4

            position = int(segment_base + (chaos_val - 0.5) * segment_variance)

            position = max(safe_start, min(safe_end, position))

            positions.append(position)

        positions.sort()

        cleaned_positions = []
        last_pos = safe_start
        for pos in positions:
            if pos - last_pos >= 5:
                cleaned_positions.append(pos)
                last_pos = pos

        return cleaned_positions

    def get_jitter_delay(self, base_ms: float = 1.0, variance: float = 2.0) -> float:

        chaos_val = self._mix_entropy()

        if chaos_val < 0.7:
            delay = base_ms + chaos_val * variance * 0.3
        else:
            delay = base_ms + variance * (chaos_val - 0.7) / 0.3

        return delay / 1000.0

    def reseed(self):

        self._initialize_state()

    def calculate_lyapunov_exponent(self, samples=100):
        if len(self.history) < samples:
            return self.last_lyapunov

        recent = list(self.history)[-samples:]

        lyap_sum = 0.0
        for i in range(len(recent) - 1):
            dx = abs(recent[i+1] - recent[i])
            if dx > 1e-10:
                lyap_sum += math.log(abs(self.r * (1 - 2 * recent[i])))

        self.last_lyapunov = lyap_sum / (len(recent) - 1) if len(recent) > 1 else 0.0
        return self.last_lyapunov

    def calculate_shannon_entropy(self, bins=256):
        if len(self.history) < 10:
            return self.last_entropy

        recent = list(self.history)[-1000:]

        hist, _ = np.histogram(recent, bins=bins, range=(0, 1))
        hist = hist / len(recent)

        entropy = 0.0
        for p in hist:
            if p > 0:
                entropy -= p * math.log2(p)

        self.last_entropy = entropy
        return entropy

    def calculate_correlation_dimension(self, r=0.1):
        if len(self.history) < 50:
            return self.last_correlation_dim

        recent = np.array(list(self.history)[-500:])

        diff = np.abs(recent[:, None] - recent[None, :])
        count = np.sum(diff < r) - len(recent)
        total_pairs = len(recent) * (len(recent) - 1)
        correlation = count / total_pairs if total_pairs > 0 else 0

        if correlation > 0:
            self.last_correlation_dim = math.log(correlation) / math.log(r)

        return self.last_correlation_dim

    def get_chaos_metrics(self):
        return {
        'lyapunov_exponent': self.calculate_lyapunov_exponent(),
        'shannon_entropy': self.calculate_shannon_entropy(),
        'correlation_dimension': self.calculate_correlation_dimension(),
        'samples_collected': len(self.history)
        }