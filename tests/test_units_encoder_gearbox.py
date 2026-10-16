"""G2.5: units, encoder, gearbox."""

import math

import numpy as np
import pytest

from models.encoder import Encoder, EncoderParams
from models.gearbox import Gearbox, GearboxParams
from models import units


# ----------------------------------------------------------------------------- units
@pytest.mark.parametrize("fn_to,fn_from,x", [
    (units.rpm_to_rad_s, units.rad_s_to_rpm, 18000.0),
    (units.rpm_to_rad_s, units.rad_s_to_rpm, 0.0),
    (units.rpm_to_rad_s, units.rad_s_to_rpm, -50.0),
])
def test_round_trips(fn_to, fn_from, x):
    assert fn_from(fn_to(x)) == pytest.approx(x, abs=1e-9)


def test_datasheet_conversions():
    assert units.rpm_to_rad_s(18000) == pytest.approx(1884.9556, abs=1e-4)
    assert units.rpm_to_rad_s(60) == pytest.approx(2 * math.pi)
    assert units.kgcm_to_Nm(27.18) == pytest.approx(2.66545, abs=1e-5)
    assert units.kgcm_to_Nm(12.5) == pytest.approx(1.22583, abs=1e-5)
    assert units.gcm_to_Nm(151) == pytest.approx(0.0148080, abs=1e-7)
    assert units.gcm_to_Nm(1000) == pytest.approx(units.kgcm_to_Nm(1))


# ----------------------------------------------------------------------------- encoder
CPR = 9360   # datasheet value; the Encoder takes it explicitly (no default), tests pass it on purpose


def _enc(noise=0.0, seed=0):
    return Encoder(EncoderParams(counts_per_rev=CPR, noise_std_rad=noise), np.random.default_rng(seed))


def test_encoder_has_no_default_cpr():
    with pytest.raises(TypeError):
        EncoderParams()


def test_quantisation_to_cpr_counts():
    e = _enc()
    lsb = 2 * math.pi / CPR
    assert e.read(2 * math.pi) == pytest.approx(2 * math.pi)                  # one output turn = 9360 counts exactly
    for k in (0, 1, 7, 4680, 9360):
        assert e.read(k * lsb) == pytest.approx(k * lsb, abs=1e-12)
    assert e.read(0.4 * lsb) == 0.0 and e.read(0.6 * lsb) == pytest.approx(lsb)  # rounds to nearest count
    assert e.read(-0.6 * lsb) == pytest.approx(-lsb)
    counts = np.round(np.array([e.read(x) for x in np.linspace(0, 1, 50)]) / lsb)
    assert np.all(np.abs(counts - np.round(np.linspace(0, 1, 50) / lsb)) <= 1)


def test_encoder_is_multi_turn_no_wrap_at_360():
    """The output encoder reads the unwrapped joint angle: 361 deg reads 361 deg, not 1 deg (documented behaviour)."""
    e = _enc()
    assert math.degrees(e.read(math.radians(361.0))) == pytest.approx(361.0, abs=360.0 / CPR)
    assert math.degrees(e.read(math.radians(720.0))) == pytest.approx(720.0, abs=1e-9)


def test_zero_noise_by_default_is_deterministic():
    a, b = _enc(), _enc(seed=123)
    xs = np.linspace(0, 6, 200)
    assert [a.read(x) for x in xs] == [b.read(x) for x in xs]


def test_noise_statistics_with_fixed_seed():
    sigma = 3 * 2 * math.pi / CPR          # 3 counts RMS
    e = _enc(noise=sigma, seed=42)
    lsb = 2 * math.pi / CPR
    reads = np.array([e.read(1.0) for _ in range(20000)])
    counts = np.round(reads / lsb)
    assert np.std(counts) == pytest.approx(3.0, rel=0.05)
    assert abs(np.mean(counts) - 1.0 / lsb) < 0.1                           # unbiased: mean count = true position
    again = _enc(noise=sigma, seed=42)
    assert [again.read(1.0) for _ in range(5)] == list(reads[:5])             # seeded, reproducible


# ----------------------------------------------------------------------------- gearbox
def test_gearbox_ratio_and_sign():
    g = Gearbox(GearboxParams(ratio=180.0, efficiency=0.8))
    assert g.output_speed(180.0) == 1.0 and g.output_position(-360.0) == -2.0
    assert g.reflect_load_torque_to_motor(1.44) == pytest.approx(1.44 / (180 * 0.8))
    assert g.reflect_load_torque_to_motor(-1.44) == pytest.approx(-1.44 / (180 * 0.8))   # sign preserved
    assert g.reflect_load_torque_to_motor(0.0) == 0.0


def test_gearbox_efficiency_default_is_ideal():
    g = Gearbox(GearboxParams(ratio=10.0))
    assert g.reflect_load_torque_to_motor(5.0) == pytest.approx(0.5)


def test_lower_efficiency_means_more_motor_torque():
    hi = Gearbox(GearboxParams(ratio=50.0, efficiency=0.9)).reflect_load_torque_to_motor(1.0)
    lo = Gearbox(GearboxParams(ratio=50.0, efficiency=0.5)).reflect_load_torque_to_motor(1.0)
    assert lo > hi
