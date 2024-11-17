import torch
import torch.nn as nn
from qlib.utils.ste import ste_round_pass


class QuantizerLSQ(nn.Module):
	def __init__(self, group_size, bit_width, use_offset=True, initializer=None):
		super().__init__()
		self.group_size = group_size
		self.bit_width = bit_width
		self.negative_clip = -2**(bit_width-1)
		self.positive_clip = 2**(bit_width-1) - 1
		self.use_offset = use_offset
		self.initializer = initializer
		self._initialized = False
		self.step = nn.Parameter(torch.ones(1, 1), requires_grad=True)
		if self.use_offset:
			self.offset = nn.Parameter(torch.zeros(1, 1), requires_grad=True)
		else:
			self.offset = None


	def regroup(self, x):
		if self.group_size == 'tensor':
			return x.flatten()
	
		if self.group_size == 'channel':
			return x.flatten(start_dim=1)

		return x.reshape(-1, self.group_size)
	
	
	def _initialize(self, x):
		self._initialized = True
		x_grouped = self.regroup(x)

		self.step.data = torch.ones(x_grouped.shape[0], 1).to(x.device)
		if self.use_offset:
			self.offset.data = torch.zeros(x_grouped.shape[0], 1).to(x.device)
		else:
			self.offset = None
		
		if self.initializer is not None:
			self.initializer(x_grouped, self)
		else:
			with torch.no_grad():
				x_min = x_grouped.float().min(axis=-1)[0].unsqueeze(-1)
				x_max = x_grouped.float().max(axis=-1)[0].unsqueeze(-1)
				step = (x_max - x_min) / (2**self.bit_width - 1)
				self.step.copy_(step)
				if self.use_offset:
					self.offset.copy_(torch.zeros_like(self.step.data))


	def lsq_forward(self, x):
		x_scaled = x / self.step
		x_clamped = torch.clamp(x_scaled, self.negative_clip, self.positive_clip)
		x_q = ste_round_pass(x_clamped)
		x_q = self.step * x_q
		return x_q


	def quantize(self, x):
		x_shape = x.shape
		if not self._initialized:
			with torch.no_grad():
				self._initialize(x)

		x_q = self.regroup(x)
			
		if self.use_offset:
			x_q = x_q + self.offset 

		x_q = self.lsq_forward(x_q)
		
		if self.use_offset:
			x_q = x_q - self.offset
	
		return x_q.reshape(x_shape)
	

	def forward(self, x):
		x_q = self.quantize(x)
		return x_q
