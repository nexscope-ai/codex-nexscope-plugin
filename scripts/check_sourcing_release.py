"""Offline consumer-contract checks. No network, credentials or paid calls."""

import ast
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / "cli/nexscope_cli/skills"


def load(package, filename):
    path = PACKAGES / package.removeprefix("ecommerce-") / "scripts" / filename
    spec = importlib.util.spec_from_file_location(filename.replace(".", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMMON = load("ecommerce-1688-procurement", "_alibaba1688_common.py")
SEARCH = load("ecommerce-1688-product-search", "1688_product_search.py")
BILLBOARD = load("ecommerce-1688-product-billboard", "1688_product_billboard.py")
IMAGE = load("ecommerce-1688-search-by-image", "alibaba1688_image_search.py")
UPLOAD = load("ecommerce-1688-search-by-image", "upload_image.py")
DETAIL = load("ecommerce-1688-product-detail", "alibaba1688_product_detail.py")
ACTIVE = {"stores": [{"accountName": "Example buyer", "status": "ACTIVE", "expired": False}]}
ORDER = {"addressId": "987654321", "cargoParamList": [{"offerId": "123456789", "specId": "sku-spec", "quantity": 2}]}
INVOICE = {"orderId": "3309156590237728779", "amount": 30500, "invoiceType": "VATAX_COMM",
           "purchaserInvoiceTitleModel": {"titleType": "PERSONAL", "title": "Example Buyer"}}
VALID = {
    "authorizeUrl": {"accountName": "Example buyer"}, "authorizedStores": {},
    "receiveAddressList": {}, "sku": {"offerId": "123456789"},
    "orderPreview": ORDER, "createOrder": {**ORDER, "confirmCreateOrder": True},
    "paymentUrl": {"orderIdList": ["3309156590237728779"], "confirmGetPaymentUrl": True},
    "orderStatus": {"aliOrderId": "3309156590237728779"},
    "logistics": {"aliOrderId": "3309156590237728779"},
    "logisticsTrace": {"aliOrderId": "3309156590237728779", "logisticsId": "example-logistics"},
    "confirmReceive": {"aliOrderId": "3309156590237728779", "confirmReceive": True},
    "cancelOrder": {"aliOrderId": "3309156590237728779", "confirmCancel": True},
    "invoiceAmount": {"orderIds": ["3309156590237728779"]},
    "invoiceApply": {"invoiceApplyModelList": [INVOICE], "confirmApplyInvoice": True},
}


class ProcurementContract(unittest.TestCase):
    def test_all_fourteen_operations_keep_business_fields_and_confirmation(self):
        self.assertEqual(set(VALID), set(COMMON.ENDPOINTS))
        for operation, payload in VALID.items():
            with self.subTest(operation=operation):
                result = {"success": True, "orderId": "3309156590237728779"}
                responses = [result] if operation in COMMON.AUTH_PRECHECK_EXEMPT_OPERATIONS else [ACTIVE, result]
                with patch.object(COMMON, "_call_gateway_raw", side_effect=responses) as request:
                    self.assertEqual(COMMON.call_gateway(operation, copy.deepcopy(payload)), result)
                actual_operation, actual_payload = request.call_args.args
                self.assertEqual(operation, actual_operation)
                for key, value in payload.items():
                    self.assertEqual(actual_payload[key], value)
                self.assertEqual(request.call_count, len(responses))
                if operation in COMMON.ORDER_FLOW_OPERATIONS:
                    self.assertEqual(actual_payload["flow"], "general")
                if operation == "createOrder":
                    self.assertEqual(actual_payload["useRedEnvelope"], "n")

    def test_five_confirmations_require_exact_boolean_before_network(self):
        for operation, field in COMMON.CONFIRM_FIELDS.items():
            for value in (None, False, "true", 1, [], {}):
                with self.subTest(operation=operation, value=value):
                    payload = copy.deepcopy(VALID[operation])
                    payload[field] = value
                    with patch.object(COMMON, "_call_gateway_raw") as request, contextlib.redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit):
                            COMMON.call_gateway(operation, payload)
                        request.assert_not_called()

    def test_missing_required_parameters_never_reach_network(self):
        cases = [
            ("authorizeUrl", {}), ("sku", {"offerId": 123}), ("orderStatus", {"orderId": "123"}),
            ("orderPreview", {"cargoParamList": ORDER["cargoParamList"]}),
            ("orderPreview", {"addressId": "123", "cargoParamList": []}),
            ("paymentUrl", {"confirmGetPaymentUrl": True, "orderIdList": []}),
            ("invoiceAmount", {"orderIds": ["12.3"]}),
            ("invoiceApply", {"confirmApplyInvoice": True, "invoiceApplyModelList": []}),
        ]
        for operation, payload in cases:
            with self.subTest(operation=operation, payload=payload), patch.object(COMMON, "_call_gateway_raw") as request:
                with self.assertRaises(ValueError):
                    COMMON.call_gateway(operation, payload)
                request.assert_not_called()

    def test_quantity_rejects_boolean_fraction_and_zero(self):
        for quantity in (True, 1.5, 0, "2"):
            payload = copy.deepcopy(ORDER)
            payload["cargoParamList"][0]["quantity"] = quantity
            with self.assertRaises(ValueError):
                COMMON.validate_params("orderPreview", payload)

    def test_address_object_and_distribution_flow_are_preserved(self):
        payload = {"addressParam": {"fullName": "Example Buyer", "mobile": "00000000000", "address": "Example address"},
                   "cargoParamList": ORDER["cargoParamList"], "flow": "fenxiao", "isvBizType": "cross_distribution"}
        self.assertEqual(COMMON.validate_params("orderPreview", COMMON.normalize_params("orderPreview", payload)), payload)

    def test_company_invoice_requirements(self):
        invoice = copy.deepcopy(INVOICE)
        invoice["purchaserInvoiceTitleModel"]["titleType"] = "COMPANY"
        payload = {"invoiceApplyModelList": [invoice]}
        with self.assertRaises(ValueError):
            COMMON.validate_params("invoiceApply", payload)
        invoice["purchaserInvoiceTitleModel"]["taxpayerIdentify"] = "EXAMPLE-TAX-ID"
        COMMON.validate_params("invoiceApply", payload)
        invoice["invoiceType"] = "VATAX_SPEC"
        for field in ("bankName", "bankAccountId", "registerAddress", "registerPhone"):
            with self.assertRaises(ValueError):
                COMMON.validate_params("invoiceApply", payload)
            invoice["purchaserInvoiceTitleModel"][field] = "Example"
        COMMON.validate_params("invoiceApply", payload)

    def test_original_optional_fields_are_preserved_without_renaming(self):
        preview = {**ORDER, "invoiceParam": {"invoiceType": 0, "titleType": 1, "title": "Example Buyer"},
                   "useBorderLogisticsSolution": True, "crossBorderLogisticsSolutionId": "source-id"}
        creation = {**ORDER, "confirmCreateOrder": True, "fenxiaoChannel": "kuajing",
                    "useBorderLogisticsSolution": True, "crossBorderLogisticsSolutionId": "source-id"}
        for operation, payload in (("orderPreview", preview), ("createOrder", creation)):
            with patch.object(COMMON, "_call_gateway_raw", side_effect=[ACTIVE, {"success": True}]) as request:
                COMMON.call_gateway(operation, copy.deepcopy(payload))
            for key, value in payload.items():
                self.assertEqual(request.call_args.args[1][key], value)

    def test_amount_is_preserved_and_invalid_numbers_rejected(self):
        for amount in (True, 0, -1, 123.9, 30500.0, 9223372036854775808, float("nan"), float("inf"), "30500"):
            invoice = {**INVOICE, "amount": amount}
            with self.assertRaises(ValueError):
                COMMON.validate_params("invoiceApply", {"invoiceApplyModelList": [invoice]})
        params = {"invoiceApplyModelList": [INVOICE]}
        self.assertEqual(COMMON.validate_params("invoiceApply", params)["invoiceApplyModelList"][0]["amount"], 30500)

    def test_authorization_is_current_and_strict(self):
        for store in ({"status": "ACTIVE"}, {"status": "ACTIVE", "expired": True},
                      {"status": "INACTIVE", "expired": False}, {"status": "ACTIVE", "expired": "false"}):
            with patch.object(COMMON, "_call_gateway_raw", return_value={"stores": [store]}) as request:
                result = COMMON.call_gateway("sku", {"offerId": "123"})
                self.assertEqual(result["error"], "authorization_required")
                request.assert_called_once_with("authorizedStores", {})

    def test_nested_active_store_and_platform_error_are_distinct(self):
        self.assertTrue(COMMON._has_active_store({"errcode": 200, "data": ACTIVE}))
        error = {"error": "HTTP 401", "httpStatus": 401}
        with patch.object(COMMON, "_call_gateway_raw", return_value=error) as request:
            self.assertEqual(COMMON.call_gateway("sku", {"offerId": "123"}), error)
            self.assertEqual(request.call_count, 1)

    def test_no_cache_every_invocation_checks_authorization(self):
        with patch.object(COMMON, "_call_gateway_raw", side_effect=[ACTIVE, {"offerId": "123"}] * 2) as request:
            COMMON.call_gateway("sku", {"offerId": "123"})
            COMMON.call_gateway("sku", {"offerId": "123"})
            self.assertEqual(request.call_count, 4)

    def test_double_envelope_preserves_preview_failure(self):
        response = COMMON.unwrap_response({"code": 0, "msg": "Too few units", "traceId": "example",
                                           "data": {"errcode": 200, "data": {"status": False, "sumPayment": 0}}})
        self.assertTrue(COMMON.business_failed(response))
        self.assertEqual(response["_nexscope"]["traceId"], "example")
        self.assertEqual(response["data"]["sumPayment"], 0)

    def test_mixed_invoice_results_are_not_discarded(self):
        business = {"success": False, "successList": [{"orderId": "123", "result": True}],
                    "failedList": [{"orderId": "124", "errorCode": "INVOICE_ALREADY_APPLIED"}]}
        response = COMMON.unwrap_response({"code": 0, "msg": None, "data": business})
        self.assertTrue(COMMON.business_failed(response))
        self.assertEqual(response["successList"], business["successList"])
        self.assertEqual(response["failedList"], business["failedList"])

    def test_platform_code_is_exact_numeric_zero(self):
        for code in ("0", False, 200, 401):
            self.assertTrue(COMMON.business_failed(COMMON.unwrap_response({"code": code, "data": ACTIVE})))

    def test_legacy_provider_error_and_batch_summary_remain_visible(self):
        self.assertTrue(COMMON.business_failed({"code": 1003, "message": "Upstream failed"}))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            COMMON.summarize({"data": {"successList": [{"orderId": "123"}], "failedList": [{"orderId": "124"}]}})
        self.assertIn("successList: 1 rows", output.getvalue())
        self.assertIn("failedList: 1 rows", output.getvalue())

    def test_transport_uses_nexscope_key_path_and_billing(self):
        class Response:
            headers = {"X-Cost-Credit": "3", "X-Kong-Trace-Id": "example-trace"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self):
                return b'{"code":0,"msg":null,"data":{"authorizeUrl":"https://example.invalid/oauth"}}'

        with patch.dict(os.environ, {"NEXSCOPE_API_KEY": "example-test-key", "NEXSCOPE_PROXY_BASE": "https://example.invalid"}):
            with patch.object(COMMON, "urlopen", return_value=Response()) as request:
                result = COMMON._call_gateway_raw("authorizeUrl", VALID["authorizeUrl"])
                sent = request.call_args.args[0]
                self.assertEqual(sent.full_url, "https://example.invalid/api/v1/tools/research/alibaba1688/authorizeUrl")
                self.assertEqual(sent.get_header("Authorization"), "Bearer example-test-key")
                self.assertEqual(result["_billing"]["X-Cost-Credit"], "3")

    def test_ambiguous_write_is_never_retried(self):
        with patch.dict(os.environ, {"NEXSCOPE_API_KEY": "example-test-key"}):
            with patch.object(COMMON, "urlopen", side_effect=URLError("timeout")) as request:
                result = COMMON._call_gateway_raw("createOrder", VALID["createOrder"])
                self.assertIn("Connection failed", result["error"])
                request.assert_called_once()

    def test_large_output_can_be_saved_with_redacted_secrets(self):
        payload = {"items": [{"id": str(index)} for index in range(1000)],
                   "access_token": "secret", "nested": {"appSecret": "secret", "tokenExpiresAt": "hidden"}}
        with tempfile.TemporaryDirectory(dir=ROOT) as directory, patch.object(COMMON, "_nexscope_root", return_value=directory):
            path, sanitized = COMMON.save_response("sku", payload)
            saved = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(saved, sanitized)
            self.assertEqual(len(saved["items"]), 1000)
            self.assertEqual(saved["access_token"], "***REDACTED***")
            self.assertNotIn("tokenExpiresAt", saved["nested"])

    def test_cli_invalid_payload_fails_before_key_or_network(self):
        script = PACKAGES / "1688-procurement/scripts/order_status.py"
        completed = subprocess.run([sys.executable, "-B", str(script), '{"orderId":"123"}'],
                                   capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("invalid_parameter", completed.stderr)


class DiscoveryContract(unittest.TestCase):
    def test_search_uses_chinese_keywords_and_comma_ids(self):
        SEARCH.validate_params({"keyWord": "\u745c\u4f3d\u57ab", "pageSize": 20, "cycle": "30"})
        SEARCH.validate_params({"productIds": "123,456"})
        for payload in ({"keyWord": "yoga mat"}, {"productIds": "123\u3001456"}, {"pageSize": 9}, {"cycle": 30}):
            with self.assertRaises(ValueError):
                SEARCH.validate_params(payload)

    def test_billboard_uses_enumeration_delimiter(self):
        BILLBOARD.validate_params({"keyWord": "\u624b\u673a\u58f3", "productIds": "123\u3001456", "pageType": 2})
        for payload in ({"productIds": "123,456"}, {"date": "2026-10-19", "pageType": 2},
                        {"date": "2026-10-02", "pageType": 3}, {"date": "2020-01-05", "pageType": 2}):
            with self.assertRaises(ValueError):
                BILLBOARD.validate_params(payload)

    def test_image_input_pagination_and_sort_contract(self):
        IMAGE.validate_params({"imageId": "example-image", "page": 2, "sort": '{"price":"asc"}'})
        IMAGE.validate_params({"imageUrl": "https://example.invalid/image.jpg", "filter": "1688Selection,qrr0"})
        for payload in ({}, {"imageId": "example", "imageUrl": "https://example.invalid/image.jpg"},
                        {"imageId": "example", "sort": {"price": "asc"}},
                        {"imageId": "example", "pageSize": 51},
                        {"imageId": "example", "filter": "invented"},
                        {"imageUrl": "https://example.invalid/image.webp"},
                        {"imageBase64": "data:image/png;base64,abcd"}):
            with self.assertRaises(ValueError):
                IMAGE.validate_params(payload)

    def test_image_upload_rejects_unsupported_bytes_before_network(self):
        with patch.object(UPLOAD, "_api_post") as request:
            self.assertTrue(UPLOAD.upload_bytes(b"GIF89aexample", "example.gif", "image/gif", "https://example.invalid", "key")["error"])
            request.assert_not_called()

    def test_detail_rejects_unsafe_ids_and_unknown_parameters(self):
        DETAIL.validate_params({"offerId": "1040473674152", "currency": "USD"})
        for payload in ({"offerId": 1040473674152}, {"offerId": "0"}, {"offerId": "123", "currency": "US"},
                        {"offerId": "123", "unknown": "value"}):
            with self.assertRaises(ValueError):
                DETAIL.validate_params(payload)


class PackageIntegrity(unittest.TestCase):
    def test_manifest_files_and_python_syntax(self):
        for directory in PACKAGES.glob("1688-*"):
            with self.subTest(package=directory.name):
                manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["name"], "ecommerce-" + directory.name)
                self.assertIn("name: ecommerce-" + directory.name, (directory / "SKILL.md").read_text(encoding="utf-8"))
                for filename in manifest["files"]:
                    self.assertTrue((directory / filename).is_file(), filename)
                for script in (directory / "scripts").glob("*.py"):
                    self.assertIn(script.relative_to(directory).as_posix(), manifest["files"])
                    ast.parse(script.read_text(encoding="utf-8"), filename=str(script))

    def test_procurement_has_no_supplier_credentials_or_account_dependencies(self):
        directory = PACKAGES / "1688-procurement"
        for filename in json.loads((directory / "manifest.json").read_text())["files"]:
            if filename == "references/1688-authorization-reference-en.png":
                self.assertTrue((directory / filename).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), filename)
                continue
            text = (directory / filename).read_text(encoding="utf-8")
            self.assertNotIn("LINKFOX", text)
            self.assertNotIn("linkfox.com", text)
            self.assertFalse(any("\u4e00" <= char <= "\u9fff" for char in text), filename)


if __name__ == "__main__":
    unittest.main()
