/* Создание события в Yandex Calendar через CalDAV PUT */
const eventData = $input.first().json;

const options = {
  method: 'PUT',
  url: eventData.caldav_url,
  headers: {
    'Content-Type': 'text/calendar; charset=utf-8',
    'Authorization': eventData.auth_header
  },
  body: eventData.ical_body,
  encoding: 'utf8',
  skipSslCertificateVerification: true,
  returnFullResponse: true,
  timeout: 30000
};

let statusCode = 0;
let responseBody = '';
let errorMessage = '';

try {
  const response = await this.helpers.httpRequest(options);
  // httpRequest with returnFullResponse returns { statusCode, body, headers }
  if (response && typeof response.statusCode === 'number') {
    statusCode = response.statusCode;
    responseBody = typeof response.body === 'string' ? response.body : JSON.stringify(response.body);
  } else {
    // Если вернулся 直接 body (не full response)
    statusCode = 200;
    responseBody = String(response);
  }
} catch (err) {
  // Ошибка может содержать statusCode
  statusCode = err.statusCode || 0;
  responseBody = err.message || String(err);
  errorMessage = err.message || String(err);
}

return [{
  json: {
    statusCode: statusCode,
    body: responseBody,
    error: errorMessage,
    caldav_url: eventData.caldav_url,
    event_uid: eventData.event_uid,
    status: (statusCode === 201 || statusCode === 204) ? 'created' : 'failed'
  }
}];