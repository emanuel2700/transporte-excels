const { test, expect } = require('@playwright/test');
const path = require('node:path');

async function login(page, username = 'operador_navegador') {
  await page.goto('/');
  await page.getByLabel('Nombre de usuario').fill(username);
  await page.getByLabel('Contraseña de demostración').fill('contraseña ficticia');
  await page.getByRole('button', { name: 'Ingresar a la plataforma' }).click();
  await expect(page.getByRole('navigation', { name: 'Navegación principal' })).toBeAttached();
}

async function navigate(page, name) {
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('link', { name, exact: true }).click();
}

test('registro manual, pago parcial, historial y anulación', async ({ page }) => {
  const failures = [];
  page.on('pageerror', error => failures.push(error.message));
  await login(page);
  await navigate(page, 'Multas');
  await page.getByRole('button', { name: 'Nueva multa' }).click();
  const dialog = page.getByRole('dialog');
  const code = `MUL-${String(Date.now()).padStart(14, '0')}`;
  await dialog.getByLabel('Código de multa').fill(code);
  await dialog.getByLabel('DNI del infractor').fill('01234567');
  await dialog.getByLabel('Tipo de infracción').selectOption('EXCESO_VELOCIDAD');
  await dialog.getByLabel('Descripción').fill('Registro ficticio creado por prueba de navegador');
  await dialog.getByLabel('Fecha de infracción').fill('2025-01-01');
  await dialog.getByLabel('Lugar de infracción').fill('Avenida de prueba');
  await dialog.getByLabel('Monto de la multa').fill('200');
  await dialog.getByLabel('Fecha de registro').fill('2025-01-02');
  await dialog.getByLabel('Fecha de vencimiento').fill('2025-02-01');
  await dialog.getByRole('button', { name: 'Registrar multa', exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByRole('button', { name: code, exact: true })).toBeVisible();

  await navigate(page, 'Pagos');
  await page.getByRole('button', { name: 'Nuevo pago' }).click();
  await dialog.getByLabel(/^Código de multa/).fill(code);
  await dialog.getByRole('button', { name: 'Buscar multa por código' }).click();
  await expect(dialog.getByLabel('DNI del infractor')).toHaveValue('01234567');
  await expect(dialog.getByText(/Saldo:/)).toBeVisible();
  await dialog.getByLabel('Fecha de pago').fill('2025-01-03');
  await dialog.getByLabel('Monto pagado').fill('75');
  await dialog.getByLabel('Método de pago').selectOption('EFECTIVO');
  const receipt = `E2E-${Date.now()}`;
  await dialog.getByLabel('Número de comprobante').fill(receipt);
  await dialog.getByRole('button', { name: 'Registrar pago', exact: true }).click();
  await expect(dialog).not.toBeVisible();

  await navigate(page, 'Multas');
  await page.getByRole('button', { name: code, exact: true }).click();
  await expect(dialog.locator('.detail-summary .badge')).toHaveText('parcial');
  await expect(dialog.getByText('operador_navegador', { exact: true })).toBeVisible();
  await expect(dialog.getByText(receipt, { exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-results/multa-desktop.png', fullPage: true });
  await dialog.getByRole('button', { name: 'Cerrar', exact: true }).click();

  await navigate(page, 'Pagos');
  await page.getByRole('button', { name: `Anular ${receipt}`, exact: true }).click();
  await dialog.getByLabel('Motivo').fill('Corrección ficticia para prueba de trazabilidad');
  await dialog.getByRole('button', { name: 'Confirmar anulación' }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByLabel('Incluir anulados').check();
  await page.getByRole('button', { name: 'Filtrar', exact: true }).click();
  const row = page.getByRole('row').filter({ has: page.getByRole('button', { name: receipt, exact: true }) });
  await expect(row.locator('.badge')).toHaveText('anulado');
  expect(failures).toEqual([]);
});

test('CSV: corregir, revalidar, confirmar y recuperar el resultado', async ({ page }) => {
  await login(page, 'usuario_importacion');
  await navigate(page, 'Importaciones');
  await page.getByLabel('Archivo CSV').setInputFiles(path.resolve(__dirname, '../../examples/csv/multas_con_errores.csv'));
  await page.getByRole('button', { name: 'Validar y revisar archivo' }).click();
  await expect(page.getByRole('heading', { name: 'Revisión de filas' })).toBeVisible();
  await expect(page.locator('.summary-card.red strong')).toHaveText('1');
  await page.getByRole('button', { name: 'Editar fila 3', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('DNI del infractor').fill('12345678');
  await dialog.getByLabel('Tipo de infracción').selectOption('DOCUMENTACION');
  await dialog.getByLabel('Fecha de infracción').fill('2025-01-10');
  await dialog.getByLabel('Monto de la multa').fill('100.00');
  await dialog.getByLabel('Fecha de vencimiento').fill('2025-02-01');
  await dialog.getByRole('button', { name: 'Guardar y validar fila' }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator('.summary-card.red strong')).toHaveText('0');
  await page.getByRole('button', { name: 'Volver a validar', exact: true }).click();
  await expect(page.getByText('Validación actualizada contra los registros actuales.')).toBeVisible();
  await page.screenshot({ path: 'test-results/importacion-desktop.png', fullPage: true });
  await page.getByRole('button', { name: 'Confirmar filas válidas' }).click();
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: 'Importar registros' }).click();
  await expect(page.getByText('Importación completada.', { exact: true })).toBeVisible();
  await expect(page.getByText(/Se guardaron 2 registros/)).toBeVisible();
  await page.getByRole('button', { name: 'Volver', exact: true }).click();
  await page.getByRole('tab', { name: 'Historial y borradores' }).click();
  await page.getByRole('button', { name: 'multas_con_errores.csv', exact: true }).click();
  await expect(page.getByText('Importación completada.', { exact: true })).toBeVisible();
});

test('móvil: login, navegación e importación cancelada sin registros definitivos', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, 'operador_movil');
  await page.screenshot({ path: 'test-results/inicio-mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.getByRole('button', { name: 'Abrir menú' }).click();
  await navigate(page, 'Importaciones');
  await page.getByLabel('Archivo CSV').setInputFiles(path.resolve(__dirname, '../../examples/csv/multas.csv'));
  await page.getByRole('button', { name: 'Validar y revisar archivo' }).click();
  await expect(page.getByRole('heading', { name: 'Revisión de filas' })).toBeVisible();
  await page.screenshot({ path: 'test-results/importacion-mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.getByRole('button', { name: 'Cancelar importación' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Descartar borrador' }).click();
  await expect(page.getByText('Importación cancelada. No se crearon registros.')).toBeVisible();
  await page.getByRole('button', { name: 'Cerrar sesión' }).click();
  await expect(page.getByLabel('Nombre de usuario')).toBeVisible();
});
