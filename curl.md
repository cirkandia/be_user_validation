POST /auth/v2/token/ HTTP/1.1
Host: apx.didit.me
Content-Type: application/x-www-form-urlencoded
Authorization: Basic ${encodedCredentials}
 
grant_type=client_credentials