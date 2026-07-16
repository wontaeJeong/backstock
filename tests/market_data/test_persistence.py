from apps.api.models import InstrumentRecord, ProviderSymbolMapping


def test_provider_symbol_mapping_keeps_effective_dated_identity() -> None:
    primary_key = tuple(column.key for column in ProviderSymbolMapping.__mapper__.primary_key)
    foreign_keys = ProviderSymbolMapping.__table__.c.instrument_id.foreign_keys

    assert primary_key == ("provider", "provider_symbol", "valid_from")
    assert len(foreign_keys) == 1
    assert InstrumentRecord.__table__.c.instrument_id.primary_key
