from app.auth.password import hash_password, verify_password


def test_hash_is_not_plaintext():
    h = hash_password("secret123")
    assert h != "secret123"
    assert len(h) > 20


def test_verify_correct_password():
    h = hash_password("correct")
    assert verify_password("correct", h) is True


def test_verify_wrong_password():
    h = hash_password("correct")
    assert verify_password("wrong", h) is False


def test_two_hashes_differ():
    # bcrypt salts randomly — same input produces different hashes
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
    assert verify_password("same", h1) is True
    assert verify_password("same", h2) is True
