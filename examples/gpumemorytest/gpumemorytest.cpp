/* Deterministic PS5 GPU compute and device-local memory test. SPDX-License-Identifier: MIT */
#include "vulkanexamplebase.h"
#include <algorithm>
#include <fstream>
#include <sstream>

class VulkanExample : public VulkanExampleBase {
public:
	struct Push { uint32_t count, base, seed, rounds; };
	VkDescriptorSetLayout setLayout{VK_NULL_HANDLE};
	VkDescriptorSet set{VK_NULL_HANDLE};
	VkPipelineLayout computeLayout{VK_NULL_HANDLE};
	VkPipeline computePipeline{VK_NULL_HANDLE};
	VkCommandPool computePool{VK_NULL_HANDLE};
	VkQueue computeQueue{VK_NULL_HANDLE};
	std::vector<std::string> lines;
	uint32_t totalErrors{0};
	bool finished{false};

	VulkanExample() : VulkanExampleBase() {
		title = "GPU Memory Test";
		apiVersion = VK_API_VERSION_1_3;
		useDynamicRendering = true;
		requiresStencil = true;
		deviceCreatepNextChain = &baseDynamicRenderingFeatures;
	}

	~VulkanExample() {
		if (!device) return;
		vkDeviceWaitIdle(device);
		vkDestroyPipeline(device, computePipeline, nullptr);
		vkDestroyPipelineLayout(device, computeLayout, nullptr);
		vkDestroyDescriptorSetLayout(device, setLayout, nullptr);
		vkDestroyCommandPool(device, computePool, nullptr);
	}

	static uint32_t expected(uint32_t index, uint32_t seed, uint32_t rounds) {
		uint32_t value = index ^ seed;
		for (uint32_t round = 0; round < rounds; ++round) {
			value ^= value >> 16; value *= 0x7feb352du;
			value ^= value >> 15; value *= 0x846ca68bu;
			value ^= value >> 16; value += 0x9e3779b9u + round;
		}
		return value;
	}

	void log(const std::string& line) {
		std::cout << "[GPU-TEST] " << line << std::endl;
		lines.push_back(line);
#if defined(__PROSPERO__)
		std::ofstream output("/app0/gpu-memory-test.log", std::ios::app);
#else
		std::ofstream output("gpu-memory-test.log", std::ios::app);
#endif
		output << line << "\n";
	}

	void prepareCompute() {
		vkGetDeviceQueue(device, vulkanDevice->queueFamilyIndices.compute, 0, &computeQueue);
		VkCommandPoolCreateInfo poolInfo = vks::initializers::commandPoolCreateInfo();
		poolInfo.queueFamilyIndex = vulkanDevice->queueFamilyIndices.compute;
		poolInfo.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
		VK_CHECK_RESULT(vkCreateCommandPool(device, &poolInfo, nullptr, &computePool));
		std::vector<VkDescriptorPoolSize> sizes = {vks::initializers::descriptorPoolSize(VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1)};
		VkDescriptorPoolCreateInfo pool = vks::initializers::descriptorPoolCreateInfo(sizes, 1);
		VK_CHECK_RESULT(vkCreateDescriptorPool(device, &pool, nullptr, &descriptorPool));
		std::vector<VkDescriptorSetLayoutBinding> bindings = {
			vks::initializers::descriptorSetLayoutBinding(VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, VK_SHADER_STAGE_COMPUTE_BIT, 0)};
		VkDescriptorSetLayoutCreateInfo setInfo = vks::initializers::descriptorSetLayoutCreateInfo(bindings);
		VK_CHECK_RESULT(vkCreateDescriptorSetLayout(device, &setInfo, nullptr, &setLayout));
		VkPushConstantRange range{VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(Push)};
		VkPipelineLayoutCreateInfo layoutInfo = vks::initializers::pipelineLayoutCreateInfo(&setLayout, 1);
		layoutInfo.pushConstantRangeCount = 1; layoutInfo.pPushConstantRanges = &range;
		VK_CHECK_RESULT(vkCreatePipelineLayout(device, &layoutInfo, nullptr, &computeLayout));
		VkDescriptorSetAllocateInfo alloc = vks::initializers::descriptorSetAllocateInfo(descriptorPool, &setLayout, 1);
		VK_CHECK_RESULT(vkAllocateDescriptorSets(device, &alloc, &set));
		VkComputePipelineCreateInfo pipelineInfo = vks::initializers::computePipelineCreateInfo(computeLayout, 0);
		pipelineInfo.stage = loadShader(getShadersPath() + "gpumemorytest/stress.comp.spv", VK_SHADER_STAGE_COMPUTE_BIT);
		VK_CHECK_RESULT(vkCreateComputePipelines(device, pipelineCache, 1, &pipelineInfo, nullptr, &computePipeline));
	}

	void runStage(uint32_t mib, uint32_t rounds, bool verifyAll) {
		const VkDeviceSize bytes = VkDeviceSize(mib) * 1024 * 1024;
		const uint32_t count = uint32_t(bytes / 4);
		const uint32_t seed = 0x51f15e5du ^ mib ^ (rounds << 16);
		vks::Buffer gpu, readback;
		VK_CHECK_RESULT(vulkanDevice->createBuffer(VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
			VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, &gpu, bytes));
		VK_CHECK_RESULT(vulkanDevice->createBuffer(VK_BUFFER_USAGE_TRANSFER_DST_BIT,
			VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT, &readback, bytes));
		VkDescriptorBufferInfo bufferInfo{gpu.buffer, 0, bytes};
		VkWriteDescriptorSet write = vks::initializers::writeDescriptorSet(set, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 0, &bufferInfo);
		vkUpdateDescriptorSets(device, 1, &write, 0, nullptr);
		VkCommandBufferAllocateInfo commandAlloc = vks::initializers::commandBufferAllocateInfo(computePool, VK_COMMAND_BUFFER_LEVEL_PRIMARY, 1);
		VkCommandBuffer command; VK_CHECK_RESULT(vkAllocateCommandBuffers(device, &commandAlloc, &command));
		VkCommandBufferBeginInfo begin = vks::initializers::commandBufferBeginInfo(); VK_CHECK_RESULT(vkBeginCommandBuffer(command, &begin));
		vkCmdBindPipeline(command, VK_PIPELINE_BIND_POINT_COMPUTE, computePipeline);
		vkCmdBindDescriptorSets(command, VK_PIPELINE_BIND_POINT_COMPUTE, computeLayout, 0, 1, &set, 0, nullptr);
		const uint32_t perDispatch = 65535u * 256u;
		for (uint32_t base = 0; base < count; base += perDispatch) {
			uint32_t part = std::min(perDispatch, count - base); Push push{count, base, seed, rounds};
			vkCmdPushConstants(command, computeLayout, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(push), &push);
			vkCmdDispatch(command, (part + 255u) / 256u, 1, 1);
		}
		VkBufferMemoryBarrier barrier = vks::initializers::bufferMemoryBarrier();
		barrier.srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT; barrier.dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
		barrier.buffer = gpu.buffer; barrier.size = bytes;
		barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED; barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
		vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, nullptr, 1, &barrier, 0, nullptr);
		VkBufferCopy copy{0, 0, bytes}; vkCmdCopyBuffer(command, gpu.buffer, readback.buffer, 1, &copy);
		VK_CHECK_RESULT(vkEndCommandBuffer(command));
		VkFence fence; VkFenceCreateInfo fenceInfo = vks::initializers::fenceCreateInfo(); VK_CHECK_RESULT(vkCreateFence(device, &fenceInfo, nullptr, &fence));
		VkSubmitInfo submit = vks::initializers::submitInfo(); submit.commandBufferCount = 1; submit.pCommandBuffers = &command;
		VK_CHECK_RESULT(vkQueueSubmit(computeQueue, 1, &submit, fence)); VK_CHECK_RESULT(vkWaitForFences(device, 1, &fence, VK_TRUE, UINT64_MAX));
		VK_CHECK_RESULT(readback.map()); const uint32_t* values = static_cast<const uint32_t*>(readback.mapped);
		uint32_t errors = 0, stride = verifyAll ? 1u : std::max(1u, count / 16384u);
		for (uint32_t i = 0; i < count; i += stride) if (values[i] != expected(i, seed, rounds)) {
			if (errors < 16) { std::ostringstream s; s << "ERROR stage=" << mib << "MiB offset=0x" << std::hex << uint64_t(i)*4 << " expected=" << expected(i,seed,rounds) << " actual=" << values[i]; log(s.str()); }
			++errors;
		}
		readback.unmap(); totalErrors += errors;
		std::ostringstream summary; summary << "stage=" << mib << "MiB rounds=" << rounds << " checked=" << ((count+stride-1)/stride) << " verdict=" << (errors?"FAIL":"PASS") << " errors=" << errors; log(summary.str());
		vkDestroyFence(device, fence, nullptr); vkFreeCommandBuffers(device, computePool, 1, &command); gpu.destroy(); readback.destroy();
	}

	void prepare() override {
		VulkanExampleBase::prepare(); prepareCompute(); log("BEGIN deterministic GPU test");
		runStage(64,4,true); runStage(128,4,true); runStage(256,4,true); runStage(64,512,false);
		log(totalErrors ? "FINAL verdict=FAIL" : "FINAL verdict=PASS"); finished=true; prepared=true;
	}
	void buildCommandBuffer() {
		VkCommandBuffer cmd=drawCmdBuffers[currentBuffer]; VkCommandBufferBeginInfo begin=vks::initializers::commandBufferBeginInfo();
		VK_CHECK_RESULT(vkBeginCommandBuffer(cmd,&begin)); beginDynamicRendering(cmd); drawUI(cmd); endDynamicRendering(cmd); VK_CHECK_RESULT(vkEndCommandBuffer(cmd));
	}
	void render() override { if(!prepared)return; VulkanExampleBase::prepareFrame(); buildCommandBuffer(); VulkanExampleBase::submitFrame(); }
	void OnUpdateUIOverlay(vks::UIOverlay* overlay) override {
		if(overlay->header("Deterministic GPU test")){ overlay->text(finished?(totalErrors?"FAIL":"PASS"):"RUNNING"); for(const auto& line:lines) overlay->text("%s",line.c_str()); if(overlay->button("Quit"))quit=true; }
	}
};
VULKAN_EXAMPLE_MAIN()
