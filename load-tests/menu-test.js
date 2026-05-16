import http from 'k6/http';
import { sleep, check } from 'k6';

export const options = {
  vus: 100,
  duration: '1m',
};

export default function () {
  const res = http.get('https://api.menly.cl/api/menu/demo-menly/');

  check(res, {
    'status 200': (r) => r.status === 200,
    'respuesta bajo 1s': (r) => r.timings.duration < 1000,
  });

  sleep(1);
}