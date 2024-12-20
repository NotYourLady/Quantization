import torch
import torch.nn as nn
from torch.nn.functional import one_hot
from qlib.quantizers.lut_quantizer import QuantizerLUT


class QuantizerLUT_autograd(QuantizerLUT):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)


	def quantize(self, x):
		x_shape = x.shape
		if not self._initialized:
			self._initialize(x.detach())

		if self.additions is not None:
			x = x + self.additions

		x_q = LUTAutograd.apply(self.regroup(x), self.levels)[0]

		x_q = x_q.reshape(x_shape)
		return x_q


class LUTAutograd(torch.autograd.Function):
	@staticmethod
	def forward(x, levels):
		borders = (levels[:, 1:] + levels[:, :-1])/2
		lut_mask = x.unsqueeze(2) > borders.unsqueeze(1)
		lut_indices = lut_mask.sum(dim=2)
		x_q = torch.take_along_dim(
			input=levels,
			indices=lut_indices,
			dim=1
			)
		return x_q, lut_indices


	@staticmethod
	def setup_context(ctx, inputs, output):
		#ctx.levels = inputs[1]
		#ctx.borders_pos = inputs[2]
		#ctx.x_q = output[0]
		ctx.lut_indices = output[1]
		ctx.set_materialize_grads(False)


	@staticmethod
	def backward(ctx, grad_output, *ignore_args): 
		if grad_output is None:
			return None, None, None

		x_grad = levels_grad = None

		if ctx.needs_input_grad[0]:
			x_grad = grad_output
		if ctx.needs_input_grad[1]:
			lut_indices = ctx.lut_indices
			lut_mask_binary = one_hot(lut_indices)
			levels_grad = (grad_output.unsqueeze(2)*lut_mask_binary).sum(dim=1)

		return x_grad, levels_grad
