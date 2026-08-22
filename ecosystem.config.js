module.exports = {
  apps: [
    {
      name: 'nodriver-rank-api',
      script: 'python3',
      args: 'api_server.py',
      cwd: '/home/tech/nodriver_rank',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1',
        TZ: 'Asia/Seoul',
        PATH: '/home/tech/.local/bin:/usr/local/bin:/usr/bin:/bin',
        LD_LIBRARY_PATH: '/home/tech/.local/lib'
      },
      error_file: '/home/tech/nodriver_rank/output/pm2_error.log',
      out_file: '/home/tech/nodriver_rank/output/pm2_out.log',
      time: true
    }
  ]
};
