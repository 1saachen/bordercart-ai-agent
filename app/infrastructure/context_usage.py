"""上下文评测的调用级计量，不采集提示词正文。"""
from contextvars import ContextVar

context_call_kind = ContextVar('context_call_kind', default='business')
context_usage_sink = ContextVar('context_usage_sink', default=None)
context_diagnostic_sink = ContextVar('context_diagnostic_sink', default=None)
context_request_details = ContextVar('context_request_details', default=None)
evaluation_evidence_sink = ContextVar('evaluation_evidence_sink', default=None)


def record_evaluation_evidence(kind, payload):
    """仅隔离评测显式安装 sink；业务默认不采集原文，也不发送到 OTLP。"""
    sink = evaluation_evidence_sink.get()
    if sink is not None:
        from copy import deepcopy
        sink({'kind': kind, 'call_kind': context_call_kind.get(), 'payload': deepcopy(payload)})


def record_context_diagnostic(event):
    """调用链诊断只传递结构化计数/状态；默认不持久化买家输入或工具正文。"""
    sink = context_diagnostic_sink.get()
    if sink is not None:
        sink(event)


def record_context_usage(input_tokens, output_tokens, elapsed_ms, *, start_time=None, ttft_ms=None):
    sample = {'kind':context_call_kind.get(), 'input_tokens':input_tokens, 'output_tokens':output_tokens, 'elapsed_ms':elapsed_ms}
    if context_request_details.get() is not None:
        sample['request_context'] = dict(context_request_details.get())
    # 非流式不能把完整响应耗时伪装成首字时间。
    sample['ttft_ms'] = ttft_ms
    sink=context_usage_sink.get()
    if sink is not None:sink(sample)
