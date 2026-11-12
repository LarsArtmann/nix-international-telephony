# The caddy-scanner failregex fixtures (L1-09): the EXACT filter text
# security.nix renders, plus caddy JSON access-log lines shaped after
# caddy 2.11's access logger. Kept beside the flake check that runs the
# real fail2ban-regex over them; if security.nix's filter ever drifts
# from this copy, mirror the change HERE in the same commit (the check
# proves the fixture, the fixture documents the filter).
{
  filter = ''
    [Definition]
    datepattern = "ts":{epoch}
    failregex = "remote_ip":"<HOST>"(?=.*"uri":"[^"]*(?:wp-login|xmlrpc\.php|/\.env|\.git|phpmyadmin|phpMyAdmin|/\.aws/|vendor/phpunit|\.asp|\.aspx|\.sql)[^"]*")(?=.*"status":4\d\d)
  '';

  hits = ''
    {"level":"info","ts":1762960000.123,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"203.0.113.7","remote_port":54321,"proto":"HTTP/1.1","method":"GET","host":"pbx.example.com","uri":"/wp-login.php","headers":{}},"status":404}
    {"level":"info","ts":1762960060.456,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"203.0.113.8","remote_port":54322,"proto":"HTTP/1.1","method":"GET","host":"pbx.example.com","uri":"/.env","headers":{}},"status":404}
    {"level":"info","ts":1762960120.789,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"203.0.113.9","remote_port":54323,"proto":"HTTP/1.1","method":"POST","host":"pbx.example.com","uri":"/xmlrpc.php","headers":{}},"status":405}
  '';

  misses = ''
    {"level":"info","ts":1762960180.111,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"198.51.100.4","remote_port":54330,"proto":"HTTP/1.1","method":"GET","host":"pbx.example.com","uri":"/wp-login.php","headers":{}},"status":200}
    {"level":"info","ts":1762960240.222,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"198.51.100.5","remote_port":54331,"proto":"HTTP/1.1","method":"GET","host":"pbx.example.com","uri":"/login","headers":{}},"status":404}
  '';
}
