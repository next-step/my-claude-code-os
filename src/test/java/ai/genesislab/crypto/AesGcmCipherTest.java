package ai.genesislab.crypto;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import ai.genesislab.testutil.UtilityClasses;
import java.security.GeneralSecurityException;
import java.security.NoSuchAlgorithmException;
import java.security.Provider;
import java.security.Security;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import javax.crypto.AEADBadTagException;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

/**
 * {@link AesGcmCipher} 단위 테스트.
 *
 * <p>키 생성·암호화·복호화의 정상·경계·예외 케이스를 검증한다.</p>
 */
@DisplayName("AesGcmCipher 단위 테스트")
class AesGcmCipherTest {

    @Nested
    @DisplayName("generateKey() — 키 생성")
    class GenerateKey {

        @Test
        @DisplayName("정상: 256-bit AES 키를 생성한다")
        void generateKey_returns256BitAesKey() {
            SecretKey key = AesGcmCipher.generateKey();

            assertNotNull(key);
            assertEquals("AES", key.getAlgorithm());
            assertEquals(32, key.getEncoded().length); // 256-bit = 32 bytes
        }

        @Test
        @DisplayName("경계: 두 번 생성하면 서로 다른 키가 나온다")
        void generateKey_calledTwice_returnsDifferentKeys() {
            SecretKey first = AesGcmCipher.generateKey();
            SecretKey second = AesGcmCipher.generateKey();

            assertNotEquals(
                    Base64.getEncoder().encodeToString(first.getEncoded()),
                    Base64.getEncoder().encodeToString(second.getEncoded()));
        }

        @Test
        @DisplayName("예외: AES KeyGenerator를 쓸 수 없으면 CryptoException(NoSuchAlgorithmException 원인)")
        void generateKey_whenAesUnavailable_throwsCryptoException() {
            // generateKey()의 방어적 catch 경로(NoSuchAlgorithmException → CryptoException 래핑)를 실행한다.
            // 표준 JVM에서는 AES가 항상 존재하므로, 이 경로를 재현하려면 KeyGenerator.AES 서비스를 제공하는
            // JCE 프로바이더를 일시적으로 제거해야 한다. 전역 상태를 건드리므로 finally에서 반드시 복원한다
            // (프로덕션 코드는 수정하지 않고, 테스트 실행 중에만 프로바이더 등록을 조정).
            List<Provider> removed = new ArrayList<>();
            for (Provider provider : Security.getProviders()) {
                if (provider.getService("KeyGenerator", AesGcmCipher.KEY_ALGORITHM) != null) {
                    removed.add(provider);
                }
            }

            try {
                for (Provider provider : removed) {
                    Security.removeProvider(provider.getName());
                }

                CryptoException ex = assertThrows(CryptoException.class, AesGcmCipher::generateKey);
                assertInstanceOf(NoSuchAlgorithmException.class, ex.getCause(),
                        "AES 알고리즘 부재는 NoSuchAlgorithmException을 원인으로 보존해야 한다");
            } finally {
                // 원상 복구: 제거한 프로바이더를 모두 되돌린다(다른 테스트에 영향 없도록).
                for (Provider provider : removed) {
                    Security.addProvider(provider);
                }
            }
        }
    }

    @Nested
    @DisplayName("encrypt(plaintext, key) — 암호화")
    class Encrypt {

        @Test
        @DisplayName("정상: 암호문은 Base64이며 IV(12바이트)+태그(16바이트)보다 길다")
        void encrypt_producesBase64WithIvPrefix() {
            SecretKey key = AesGcmCipher.generateKey();

            String ciphertext = AesGcmCipher.encrypt("hello", key);

            byte[] decoded = Base64.getDecoder().decode(ciphertext); // Base64 디코드 성공해야 함
            assertTrue(decoded.length > AesGcmCipher.IV_LENGTH_BYTES,
                    "IV 12바이트 + 암호문/태그가 포함되어야 한다");
        }

        @Test
        @DisplayName("경계: 같은 평문을 두 번 암호화하면 IV가 달라 암호문이 다르다")
        void encrypt_samePlaintextTwice_producesDifferentCiphertext() {
            SecretKey key = AesGcmCipher.generateKey();

            String first = AesGcmCipher.encrypt("same-message", key);
            String second = AesGcmCipher.encrypt("same-message", key);

            assertNotEquals(first, second);
        }

        @Test
        @DisplayName("예외: 평문이 null이면 IllegalArgumentException")
        void encrypt_nullPlaintext_throwsIllegalArgument() {
            SecretKey key = AesGcmCipher.generateKey();

            IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                    () -> AesGcmCipher.encrypt(null, key));
            assertEquals(AesGcmCipher.NULL_PLAINTEXT_MESSAGE, ex.getMessage());
        }

        @Test
        @DisplayName("예외: 키가 null이면 IllegalArgumentException")
        void encrypt_nullKey_throwsIllegalArgument() {
            IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                    () -> AesGcmCipher.encrypt("hello", null));
            assertEquals(AesGcmCipher.NULL_KEY_MESSAGE, ex.getMessage());
        }

        @Test
        @DisplayName("예외: 형식이 맞지만 유효하지 않은 키(길이 오류)는 CryptoException(GeneralSecurityException 원인)")
        void encrypt_invalidKey_throwsCryptoException() {
            // null이 아니어서 인자 검증은 통과하지만 AES 유효 길이(16/24/32B)가 아닌 키.
            // cipher.init 단계에서 InvalidKeyException(=GeneralSecurityException)이 나고,
            // encrypt의 방어적 catch가 이를 CryptoException으로 원인 보존 래핑한다.
            SecretKey invalidKey = new SecretKeySpec(new byte[7], AesGcmCipher.KEY_ALGORITHM);

            CryptoException ex = assertThrows(CryptoException.class,
                    () -> AesGcmCipher.encrypt("hello", invalidKey));
            assertInstanceOf(GeneralSecurityException.class, ex.getCause(),
                    "암호화 실패는 보안 예외를 원인으로 보존해야 한다");
        }
    }

    @Nested
    @DisplayName("decrypt(ciphertext, key) — 복호화")
    class Decrypt {

        @Test
        @DisplayName("정상: 암호화→복호화 왕복이 원문과 일치한다")
        void decrypt_roundTrip_returnsOriginal() {
            SecretKey key = AesGcmCipher.generateKey();
            String plaintext = "round-trip-message";

            String decrypted = AesGcmCipher.decrypt(AesGcmCipher.encrypt(plaintext, key), key);

            assertEquals(plaintext, decrypted);
        }

        @ParameterizedTest(name = "왕복: \"{0}\"")
        @DisplayName("경계: 빈 문자열·공백·특수문자·멀티바이트 왕복")
        @ValueSource(strings = {"", " ", "1234567890", "!@#$%^&*()", "한글 메시지", "emoji 😀 test"})
        void decrypt_variousPlaintexts_roundTrip(String plaintext) {
            SecretKey key = AesGcmCipher.generateKey();

            String decrypted = AesGcmCipher.decrypt(AesGcmCipher.encrypt(plaintext, key), key);

            assertEquals(plaintext, decrypted);
        }

        @Test
        @DisplayName("예외: 변조된 암호문은 인증 실패(AEADBadTagException 원인)로 CryptoException")
        void decrypt_tamperedCiphertext_throwsAuthFailure() {
            SecretKey key = AesGcmCipher.generateKey();
            String ciphertext = AesGcmCipher.encrypt("secret", key);

            // Base64 디코드 후 마지막 바이트(GCM 태그 일부)를 뒤집어 변조한다.
            byte[] raw = Base64.getDecoder().decode(ciphertext);
            raw[raw.length - 1] ^= 0x01;
            String tampered = Base64.getEncoder().encodeToString(raw);

            CryptoException ex = assertThrows(CryptoException.class,
                    () -> AesGcmCipher.decrypt(tampered, key));
            assertInstanceOf(AEADBadTagException.class, ex.getCause());
        }

        @Test
        @DisplayName("예외: 잘못된 키로 복호화하면 인증 실패로 CryptoException")
        void decrypt_wrongKey_throwsAuthFailure() {
            SecretKey encryptKey = AesGcmCipher.generateKey();
            SecretKey wrongKey = AesGcmCipher.generateKey();
            String ciphertext = AesGcmCipher.encrypt("secret", encryptKey);

            CryptoException ex = assertThrows(CryptoException.class,
                    () -> AesGcmCipher.decrypt(ciphertext, wrongKey));
            assertInstanceOf(AEADBadTagException.class, ex.getCause());
        }

        @Test
        @DisplayName("예외: Base64가 아닌 문자열은 형식 오류 CryptoException")
        void decrypt_invalidBase64_throwsMalformed() {
            SecretKey key = AesGcmCipher.generateKey();

            CryptoException ex = assertThrows(CryptoException.class,
                    () -> AesGcmCipher.decrypt("이건 base64 가 아님!!!", key));
            assertEquals(AesGcmCipher.MALFORMED_CIPHERTEXT_MESSAGE, ex.getMessage());
        }

        @Test
        @DisplayName("예외: IV(12바이트)보다 짧은 페이로드는 형식 오류 CryptoException")
        void decrypt_tooShortPayload_throwsMalformed() {
            SecretKey key = AesGcmCipher.generateKey();
            // 5바이트짜리 유효한 Base64 → IV 길이(12)보다 짧다.
            String tooShort = Base64.getEncoder().encodeToString(new byte[]{1, 2, 3, 4, 5});

            CryptoException ex = assertThrows(CryptoException.class,
                    () -> AesGcmCipher.decrypt(tooShort, key));
            assertEquals(AesGcmCipher.MALFORMED_CIPHERTEXT_MESSAGE, ex.getMessage());
        }

        @ParameterizedTest(name = "{0}바이트 페이로드 → MALFORMED")
        @DisplayName("결함#1: IV는 있으나 GCM 태그(16B)를 담기엔 짧은 12~27바이트는 인증실패가 아닌 형식 오류")
        @ValueSource(ints = {12, 20, 27})
        void decrypt_ivPresentButTagTooShort_classifiedAsMalformed(int payloadLength) {
            SecretKey key = AesGcmCipher.generateKey();
            // IV 길이(12) 이상이지만 IV+태그(28) 미만 → doFinal로 흘러가면 AEADBadTag("too short to contain tag")로
            // "변조"로 오분류된다. 가드가 올바르면 MALFORMED로 분류되어야 한다.
            byte[] payload = new byte[payloadLength];
            for (int i = 0; i < payloadLength; i++) {
                payload[i] = (byte) (i + 1);
            }
            String malformed = Base64.getEncoder().encodeToString(payload);

            CryptoException ex = assertThrows(CryptoException.class,
                    () -> AesGcmCipher.decrypt(malformed, key));
            // 핵심 단언: 메시지가 인증 실패(변조)가 아니라 포맷 오류여야 하고, 원인 AEADBadTagException이 없어야 한다.
            assertEquals(AesGcmCipher.MALFORMED_CIPHERTEXT_MESSAGE, ex.getMessage());
            assertTrue(!(ex.getCause() instanceof AEADBadTagException),
                    "구조적으로 짧은 페이로드는 인증 실패(AEADBadTagException)로 오분류되면 안 된다");
        }

        @Test
        @DisplayName("경계#1: 정확히 28바이트(IV12+태그16)는 정상 경로로 진입하되 키 불일치 시 인증 실패로 분류")
        void decrypt_minimumValidLength_entersCipherPathAndFailsAuth() {
            SecretKey key = AesGcmCipher.generateKey();
            // 28바이트 = IV(12) + 태그(16), 평문 0바이트에 해당하는 최소 유효 길이.
            // 가드를 통과해 cipher.doFinal로 진입하지만, 임의 바이트라 태그 검증에 실패한다 → 인증 실패(변조).
            byte[] minimumValid = new byte[AesGcmCipher.IV_LENGTH_BYTES + AesGcmCipher.GCM_TAG_LENGTH_BYTES];
            for (int i = 0; i < minimumValid.length; i++) {
                minimumValid[i] = (byte) (i + 1);
            }
            String payload = Base64.getEncoder().encodeToString(minimumValid);

            CryptoException ex = assertThrows(CryptoException.class,
                    () -> AesGcmCipher.decrypt(payload, key));
            // 28바이트는 MALFORMED가 아니라 인증 실패(AEADBadTagException 원인)로 구분되어야 한다.
            assertNotEquals(AesGcmCipher.MALFORMED_CIPHERTEXT_MESSAGE, ex.getMessage());
            assertInstanceOf(AEADBadTagException.class, ex.getCause());
        }

        @Test
        @DisplayName("예외: 암호문이 null이면 IllegalArgumentException")
        void decrypt_nullCiphertext_throwsIllegalArgument() {
            SecretKey key = AesGcmCipher.generateKey();

            IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                    () -> AesGcmCipher.decrypt(null, key));
            assertEquals(AesGcmCipher.NULL_CIPHERTEXT_MESSAGE, ex.getMessage());
        }

        @Test
        @DisplayName("예외: 키가 null이면 IllegalArgumentException")
        void decrypt_nullKey_throwsIllegalArgument() {
            IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                    () -> AesGcmCipher.decrypt("anything", null));
            assertEquals(AesGcmCipher.NULL_KEY_MESSAGE, ex.getMessage());
        }
    }

    @Test
    @DisplayName("설계: 유틸리티 클래스는 인스턴스화할 수 없다")
    void aesGcmCipher_cannotBeInstantiated() throws Exception {
        UtilityClasses.assertNotInstantiable(AesGcmCipher.class);
    }
}
