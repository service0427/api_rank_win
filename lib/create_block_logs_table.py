import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')

HOST = "114.207.112.172"
PORT = 22
USER = "tech"
PASS = "1324!"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

print("=" * 80)
print("CREATING TABLE api_block_logs ON MySQL")
print("=" * 80)

create_sql = """python3 -c "
import pymysql

conn = pymysql.connect(host='127.0.0.1', user='rank', password='Tech1324', database='rank', charset='utf8mb4')
with conn.cursor() as cur:
    cur.execute('''
        CREATE TABLE IF NOT EXISTS api_block_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            service_type VARCHAR(20) NOT NULL COMMENT 'shop / place',
            keyword VARCHAR(255) NOT NULL COMMENT '검색 키워드',
            target_code VARCHAR(100) DEFAULT NULL COMMENT '타겟 상품/업체 코드',
            status_code INT DEFAULT 418 COMMENT 'HTTP 상태코드 (418, 403, 429 등)',
            error_message TEXT COMMENT '차단 상세 메시지 / 응답 헤더',
            proxy_url VARCHAR(255) DEFAULT NULL COMMENT '사용된 프록시 URL',
            client_ip VARCHAR(50) DEFAULT NULL COMMENT '요청 클라이언트 IP',
            engine_used VARCHAR(50) DEFAULT NULL COMMENT 'PACKET / NODRIVER',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '차단 발생 일시',
            INDEX idx_created (created_at),
            INDEX idx_proxy (proxy_url),
            INDEX idx_keyword (keyword),
            INDEX idx_service (service_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='418/차단 발생 히스토리 상세 로그 테이블';
    ''')
    conn.commit()
    print('Table api_block_logs created successfully!')

    cur.execute('DESC api_block_logs;')
    for col in cur.fetchall():
        print(' ', col)

conn.close()
"
"""

stdin, stdout, stderr = ssh.exec_command(create_sql)
print(stdout.read().decode('utf-8', errors='ignore'))
print(stderr.read().decode('utf-8', errors='ignore'))

ssh.close()
