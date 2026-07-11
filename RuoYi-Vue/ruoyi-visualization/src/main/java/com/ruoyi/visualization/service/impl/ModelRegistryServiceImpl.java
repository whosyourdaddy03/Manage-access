package com.ruoyi.visualization.service.impl;

import com.ruoyi.visualization.domain.ModelRegistry;
import com.ruoyi.visualization.mapper.ModelRegistryMapper;
import com.ruoyi.visualization.service.ModelRegistryService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;

@Service
public class ModelRegistryServiceImpl implements ModelRegistryService {

    private final Logger logger = LoggerFactory.getLogger(ModelRegistryServiceImpl.class);

    @Autowired
    private ModelRegistryMapper modelRegistryMapper;

    @Override
    public List<ModelRegistry> selectModelList() {
        return modelRegistryMapper.selectModelList();
    }

    @Override
    public ModelRegistry selectModelById(Long id) {
        return modelRegistryMapper.selectModelById(id);
    }

    @Override
    public int insertModel(ModelRegistry model) {
        if (model.getStatus() == null) {
            model.setStatus("archived");
        }
        return modelRegistryMapper.insertModel(model);
    }

    @Override
    public int updateModel(ModelRegistry model) {
        return modelRegistryMapper.updateModel(model);
    }

    @Override
    public int deleteModelById(Long id) {
        return modelRegistryMapper.deleteModelById(id);
    }

    @Override
    public List<Map<String, String>> scanLocalModels(String dirPath) {
        return modelRegistryMapper.scanLocalModels(dirPath);
    }

    @Override
    @Transactional
    public void setInUse(Long id) {
        modelRegistryMapper.clearInUseStatus();
        modelRegistryMapper.setInUseStatus(id);
    }
}
