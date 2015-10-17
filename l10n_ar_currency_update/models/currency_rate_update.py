# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import fields, models, api, _
from openerp.exceptions import Warning
from datetime import datetime, time
from dateutil.relativedelta import relativedelta
import logging
# import openerp.addons.decimal_precision as dp
from openerp.addons.currency_rate_update.model.currency_rate_update import supported_currecies

_logger = logging.getLogger(__name__)

_intervalTypes = {
    'days': lambda interval: relativedelta(days=interval),
    'weeks': lambda interval: relativedelta(days=7*interval),
    'months': lambda interval: relativedelta(months=interval),
}

# TODO completar con todas las monedas soportadas
AFIP_WS_supported_currency_array = [
    'USD', 'EUR', 'AUD', 'CAD', 'GBP', 'JPY', 'MXN', 'UYU', 'VEF']

supported_currecies['afip_ws'] = AFIP_WS_supported_currency_array


class Currency_rate_update_service(models.Model):
    """Class keep services and currencies that
    have to be updated"""
    _inherit = "currency.rate.update.service"

    service = fields.Selection(
        selection_add=([('afip_ws', 'AFIP WS')])
        )
    rate_perc = fields.Float(
        'Rate Perc.',
        digits=(16, 4),
        # digits=dp.get_precision('Product Price'),
        )
    rate_surcharge = fields.Float(
        'Rate Surcharge',
        digits=(16, 4),
        # digits=dp.get_precision('Product Price'),
        )

    @api.one
    def refres_currency_with_afip_ws(self):
        """
        TODO: no reescribir este metodo si no que heredar de una mejor manera
        el original
        """
        _logger.info(
            'Starting to refresh currencies with service %s (company: %s)',
            self.service, self.company_id.name)
        # factory = Currency_getter_factory()
        curr_obj = self.env['res.currency']
        rate_obj = self.env['res.currency.rate']
        company = self.company_id
        # The multi company currency can be set or no so we handle
        # The two case
        if company.auto_currency_up:
            main_currency = curr_obj.search(
                [('base', '=', True), ('company_id', '=', company.id)],
                limit=1)
            if not main_currency:
                # If we can not find a base currency for this company
                # we look for one with no company set
                main_currency = curr_obj.search(
                    [('base', '=', True), ('company_id', '=', False)],
                    limit=1)
            if not main_currency:
                raise Warning(_('There is no base currency set!'))
            if main_currency.rate != 1:
                raise Warning(_('Base currency rate should be 1.00!'))
            # TODO implementar poder usar otras monedas como base
            if main_currency.name != 'ARS':
                raise Warning(_('For AFIP WS base currency must be ARS!'))
            note = self.note or ''
            try:
                rate_name = \
                    fields.Datetime.to_string(datetime.utcnow().replace(
                        hour=0, minute=0, second=0, microsecond=0))
                for curr in self.currency_to_update:
                    if curr.id == main_currency.id:
                        continue
                    rate, msg = curr.get_pyafipws_currency_rate(
                        company=self.company_id,
                        )
                    if rate:
                        rate = rate * (1.0+(self.rate_perc or 0.0))
                        rate += self.rate_surcharge or 0.0
                        rate = 1.0 / rate
                        vals = {
                            'currency_id': curr.id,
                            'rate': rate,
                            'name': rate_name
                        }
                        rate_obj.create(vals)
                        _logger.info(
                            'Updated currency %s via service %s',
                            curr.name, self.service)
                    else:
                        raise Warning(
                            'Could not update currency %s via service %s. %s',
                            curr.name, self.service, msg)

                # Show the most recent note at the top
                msg = '%s currency updated. %s' % (
                    fields.Datetime.to_string(datetime.today()),
                    note
                )
                self.write({'note': msg})
            except Exception as exc:
                error_msg = '\n%s ERROR : %s %s' % (
                    fields.Datetime.to_string(datetime.today()),
                    repr(exc),
                    note
                )
                _logger.error(repr(exc))
                self.write({'note': error_msg})
            if self._context.get('cron', False):
                midnight = time(0, 0)
                next_run = (datetime.combine(
                            fields.Date.from_string(self.next_run),
                            midnight) +
                            _intervalTypes[str(self.interval_type)]
                            (self.interval_number)).date()
                self.next_run = next_run

    @api.one
    def refresh_currency(self):
        if self.service == 'afip_ws':
            return self.refres_currency_with_afip_ws()
        else:
            return super(Currency_rate_update_service, self).refresh_currency()
