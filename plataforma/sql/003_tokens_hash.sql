-- Fase 7 (feature/trabajos-y-sesiones): los ids de sesion y los tokens de un
-- uso se guardan como su SHA-256, no en claro. Lo que viaja en la cookie o en
-- el enlace sigue siendo el valor original; quien lea la base (backup,
-- replica, /admin) ya no obtiene sesiones ni tokens de reset listos para
-- usar. Idempotente: solo se transforma lo que aun no es un hash (64 hex).
UPDATE pliego.sesiones SET id = encode(sha256(convert_to(id, 'UTF8')), 'hex') WHERE id !~ '^[0-9a-f]{64}$';
UPDATE pliego.tokens   SET id = encode(sha256(convert_to(id, 'UTF8')), 'hex') WHERE id !~ '^[0-9a-f]{64}$';
